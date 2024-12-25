import secrets
from base64 import b64encode, b64decode
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest
from algosdk.logic import get_application_address
from algosdk.encoding import encode_address, decode_address
from algosdk.transaction import SuggestedParams, Transaction
from algosdk.box_reference import BoxReference
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
    EmptySigner,
)
from ..transaction_utils import (
    signer,
    sp_fee,
    remove_signer_and_group,
    transferAlgoOrAsset,
)
from ..lending.v2.mathlib import mulScale
from ..state_utils import get_global_state, get_application_box, parse_uint64s
from .constants.mainnet_constants import MAINNET_RESERVE_ADDRESS
from .abi_contracts import xAlgoABIContract
from .datatypes import ConsensusConfig, ConsensusState, ProposerBalance
from .allocation_strategies.greedy import (
    greedyStakeAllocationStrategy as defaultStakeAllocationStrategy,
    greedyUnstakeAllocationStrategy as defaultUnstakeAllocationStrategy,
)


def getConsensusState(
    algodClient: AlgodClient, consensusConfig: ConsensusConfig
) -> ConsensusState:
    """
    Returns information regarding the given consensus application.

    @param algodClient - Algorand client to query
    @param consensusConfig - consensus application and xALGO config
    @returns ConsensusState current state of the consensus application
    """

    state = get_global_state(algodClient, consensusConfig.appId)
    box = get_application_box(algodClient, consensusConfig.appId, "pr".encode())
    current_round = box["round"]
    boxValue = b64decode(box["value"])
    params = algodClient.suggested_params()
    if not state:
        raise ValueError("Could not find xAlgo application")

    # xALGO rate
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=MAINNET_RESERVE_ADDRESS,
        signer=EmptySigner(),
        app_id=consensusConfig.appId,
        method=xAlgoABIContract.get_method_by_name("get_xalgo_rate"),
        method_args=[],
        sp=params,
    )
    simReq = SimulateRequest(
        txn_groups=[],
        allow_empty_signatures=True,
        allow_unnamed_resources=True,
        extra_opcode_budget=70000,
    )
    methodResults = atc.simulate(algodClient, simReq).abi_results
    returnValue = methodResults[0].return_value
    algoBalance, xAlgoCirculatingSupply, balances = returnValue

    # proposers
    proposersBalances = [
        ProposerBalance(encode_address(boxValue[i * 32 : (i + 1) * 32]), balance)
        for i, balance in enumerate(parse_uint64s(b64encode(bytes(balances))))
    ]

    # global state
    timeDelay = int(state.get("time_delay", 0))
    numProposers = int(state.get("num_proposers", 0))
    minProposerBalance = int(state.get("min_proposer_balance", 0))
    maxProposerBalance = int(state.get("max_proposer_balance", 0))
    fee = int(state.get("fee", 0))
    premium = int(state.get("premium", 0))
    totalPendingStake = int(state.get("total_pending_stake", 0))
    totalActiveStake = int(state.get("total_active_stake", 0))
    totalRewards = int(state.get("total_rewards", 0))
    totalUnclaimedFees = int(state.get("total_unclaimed_fees", 0))
    canImmediateStake = bool(state.get("can_immediate_mint"))
    canDelayStake = bool(state.get("can_delay_mint"))

    return ConsensusState(
        current_round,
        algoBalance,
        xAlgoCirculatingSupply,
        proposersBalances,
        timeDelay,
        numProposers,
        minProposerBalance,
        maxProposerBalance,
        fee,
        premium,
        totalPendingStake,
        totalActiveStake,
        totalRewards,
        totalUnclaimedFees,
        canImmediateStake,
        canDelayStake,
    )


def prepareDummyTransaction(
    consensusConfig: ConsensusConfig,
    senderAddr: str,
    params: SuggestedParams,
) -> Transaction:
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=consensusConfig.appId,
        method=xAlgoABIContract.get_method_by_name("dummy"),
        method_args=[],
        sp=sp_fee(params, fee=3000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


# assumes txns has either structure:
# period 1 [appl call, appl call, ...]
# period 2 [transfer, appl call, transfer, appl call, ...]
def getTxnsAfterResourceAllocation(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    txnsToAllocateTo: list[Transaction],
    additionalAddresses: list[str],
    period: int,
    senderAddr: str,
    params: SuggestedParams,
) -> list[Transaction]:
    appId = consensusConfig.appId
    xAlgoId = consensusConfig.xAlgoId

    # make copy of txns
    txns = txnsToAllocateTo.copy()

    if len(txns) % period != 0:
        raise ValueError(f"Number of txns is not multiple of {period}")
    availableCalls = len(txns) // period

    # add xALGO asset and proposers box
    t1 = txns[period - 1]
    t1.foreign_assets = [xAlgoId]
    t1.boxes.append((appId, "pr".encode()))
    t1.boxes = BoxReference.translate_box_references(
        t1.boxes, t1.foreign_apps, t1.index
    )

    # get all accounts we need to add
    accounts: list[str] = additionalAddresses
    accounts += [proposer.address for proposer in consensusState.proposersBalances]

    # add accounts in groups of 4
    MAX_FOREIGN_ACCOUNT_PER_TXN = 4
    for i in range(0, len(accounts), MAX_FOREIGN_ACCOUNT_PER_TXN):
        # which txn to use
        callNum = i // MAX_FOREIGN_ACCOUNT_PER_TXN + 1

        # check if we need to add dummy call
        if callNum <= availableCalls:
            txnIndex = callNum * period - 1
        else:
            txns.insert(0, prepareDummyTransaction(consensusConfig, senderAddr, params))
            txnIndex = 0

        # add proposer accounts
        txns[txnIndex].accounts = accounts[i : i + 4]

    return txns


def prepareImmediateStakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    amount: int,
    minReceivedAmount: int,
    params: SuggestedParams,
    proposerAllocationStrategy=defaultStakeAllocationStrategy,
    note: bytes | None = None,
) -> list[Transaction]:
    """
    Returns a group transaction to stake ALGO and get xALGO immediately.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param amount - amount of ALGO to send
    @param minReceivedAmount - min amount of xALGO expected to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param proposerAllocationStrategy - determines which proposers the ALGO sent goes to
    @param note - optional note to distinguish who is the minter (must pass to be eligible for revenue share)
    @returns Transaction[] stake transactions
    """
    appId = consensusConfig.appId

    atc = AtomicTransactionComposer()
    proposerAllocations = proposerAllocationStrategy(consensusState, amount)

    for proposerIndex, splitMintAmount in enumerate(proposerAllocations):
        if splitMintAmount == 0:
            continue

        # calculate min received amount by proportional of total mint amount
        splitMinReceivedAmount = mulScale(minReceivedAmount, splitMintAmount, amount)

        # generate txns for single proposer
        proposerAddress = consensusState.proposersBalances[proposerIndex].address
        sendAlgo = transferAlgoOrAsset(
            0, senderAddr, proposerAddress, splitMintAmount, params
        )
        atc.add_method_call(
            sender=senderAddr,
            signer=signer,
            app_id=appId,
            method=xAlgoABIContract.get_method_by_name("immediate_mint"),
            method_args=[
                TransactionWithSigner(sendAlgo, signer),
                proposerIndex,
                splitMinReceivedAmount,
            ],
            sp=sp_fee(params, fee=2000),
            note=note,
        )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    return getTxnsAfterResourceAllocation(
        consensusConfig, consensusState, txns, [], 2, senderAddr, params
    )


def prepareDelayedStakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    amount: int,
    params: SuggestedParams,
    includeBoxMinBalancePayment: bool = True,
    proposerAllocationStrategy=defaultStakeAllocationStrategy,
    note: bytes | None = None,
) -> list[Transaction]:
    """
    Returns a group transaction to stake ALGO and get xALGO after 320 rounds.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param amount - amount of ALGO to send
    @param params - suggested params for the transactions with the fees overwritten
    @param includeBoxMinBalancePayment - whether to include ALGO payment to app for box min balance
    @param proposerAllocationStrategy - determines which proposers the ALGO sent goes to
    @param note - optional note to distinguish who is the minter (must pass to be eligible for revenue share)
    @returns Transaction[] stake transactions
    """
    appId = consensusConfig.appId

    atc = AtomicTransactionComposer()
    proposerAllocations = proposerAllocationStrategy(consensusState, amount)

    for proposerIndex, splitMintAmount in enumerate(proposerAllocations):
        if splitMintAmount == 0:
            continue

        # generate txns for single proposer
        proposerAddress = consensusState.proposersBalances[proposerIndex].address
        sendAlgo = transferAlgoOrAsset(
            0, senderAddr, proposerAddress, splitMintAmount, params
        )
        nonce = secrets.token_bytes(2)  # TODO: safeguard against possible clash?
        boxName = "dm".encode() + decode_address(senderAddr) + nonce
        atc.add_method_call(
            sender=senderAddr,
            signer=signer,
            app_id=appId,
            method=xAlgoABIContract.get_method_by_name("delayed_mint"),
            method_args=[TransactionWithSigner(sendAlgo, signer), proposerIndex, nonce],
            boxes=[(appId, boxName)],
            sp=sp_fee(params, fee=2000),
            note=note,
        )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    txns = getTxnsAfterResourceAllocation(
        consensusConfig, consensusState, txns, [], 2, senderAddr, params
    )

    # add box min balance payment if specified
    if includeBoxMinBalancePayment:
        minBalance = 36100
        appAddr = get_application_address(appId)
        txns = [transferAlgoOrAsset(0, senderAddr, appAddr, minBalance, params)] + txns

    return txns


def prepareClaimDelayedStakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    receiverAddr: str,
    nonce: bytes,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to claim xALGO from delayed stake after 320 rounds.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param receiverAddr - account address for the receiver
    @param nonce - what was used to generate the delayed mint box
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] stake transactions
    """
    appId = consensusConfig.appId

    atc = AtomicTransactionComposer()
    boxName = "dm".encode() + decode_address(receiverAddr) + nonce
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=appId,
        method=xAlgoABIContract.get_method_by_name("claim_delayed_mint"),
        method_args=[receiverAddr, nonce],
        boxes=[(appId, boxName)],
        sp=sp_fee(params, fee=3000),
    )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    return getTxnsAfterResourceAllocation(
        consensusConfig,
        consensusState,
        txns,
        [receiverAddr],
        1,
        senderAddr,
        params,
    )


def prepareUnstakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    amount: int,
    minReceivedAmount: int,
    params: SuggestedParams,
    proposerAllocationStrategy=defaultUnstakeAllocationStrategy,
    note: bytes | None = None,
) -> list[Transaction]:
    """
    Returns a group transaction to unstake xALGO and get ALGO.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param amount - amount of xALGO to send
    @param minReceivedAmount - min amount of ALGO expected to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param proposerAllocationStrategy - determines which proposers the ALGO received comes from
    @param note - optional note to distinguish who is the burner (must pass to be eligible for revenue share)
    @returns Transaction[] unstake transactions
    """
    appId = consensusConfig.appId
    xAlgoId = consensusConfig.xAlgoId

    atc = AtomicTransactionComposer()
    proposerAllocations = proposerAllocationStrategy(consensusState, amount)

    for proposerIndex, splitBurnAmount in enumerate(proposerAllocations):
        if splitBurnAmount == 0:
            continue

        # calculate min received amount by proportional of total burn amount
        splitMinReceivedAmount = mulScale(minReceivedAmount, splitBurnAmount, amount)

        # generate txns for single proposer
        sendXAlgo = transferAlgoOrAsset(
            xAlgoId, senderAddr, get_application_address(appId), splitBurnAmount, params
        )
        atc.add_method_call(
            sender=senderAddr,
            signer=signer,
            app_id=appId,
            method=xAlgoABIContract.get_method_by_name("burn"),
            method_args=[
                TransactionWithSigner(sendXAlgo, signer),
                proposerIndex,
                splitMinReceivedAmount,
            ],
            sp=sp_fee(params, fee=2000),
            note=note,
        )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    return getTxnsAfterResourceAllocation(
        consensusConfig, consensusState, txns, [], 2, senderAddr, params
    )
