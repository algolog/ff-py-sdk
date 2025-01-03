from base64 import b64encode, b64decode
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest
from algosdk.logic import get_application_address
from algosdk.encoding import encode_address, decode_address
from algosdk.transaction import SuggestedParams, Transaction, ApplicationCallTxn
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
from ..config import PAYOUTS_GO_ONLINE_FEE
from ..state_utils import get_global_state, get_application_box, parse_uint64s
from .constants.mainnet_constants import MAINNET_RESERVE_ADDRESS
from .abi_contracts import xAlgoABIContract, stakeAndDepositABIContract
from .datatypes import ConsensusConfig, ConsensusState, ProposerBalance
from ..lending.v2.datatypes import Pool


def getConsensusState(
    algodClient: AlgodClient, consensusConfig: ConsensusConfig
) -> ConsensusState:
    """
    Returns information regarding the given consensus application.

    @param algodClient - Algorand client to query
    @param consensusConfig - consensus application and xALGO config
    @returns ConsensusState current state of the consensus application
    """
    consensusAppId = consensusConfig.consensusAppId

    state = get_global_state(algodClient, consensusAppId)
    box = get_application_box(algodClient, consensusAppId, "pr".encode())
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
        app_id=consensusAppId,
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
    maxProposerBalance = int(state.get("max_proposer_balance", 0))
    fee = int(state.get("fee", 0))
    premium = int(state.get("premium", 0))
    lastProposersActiveBalance = int(state.get("last_proposers_active_balance", 0))
    totalPendingStake = int(state.get("total_pending_stake", 0))
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
        maxProposerBalance,
        fee,
        premium,
        lastProposersActiveBalance,
        totalPendingStake,
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
        app_id=consensusConfig.consensusAppId,
        method=xAlgoABIContract.get_method_by_name("dummy"),
        method_args=[],
        sp=sp_fee(params, fee=1000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def add_box_to_appcall(txn: ApplicationCallTxn, box: tuple[int, bytes]):
    """
    Appends an extra box to the list of txn boxes.
    Should be called after all foreign apps are added.
    """
    # ApplicationCallTxn.boxes is always a list, no need to check
    txn.boxes.append(box)
    # translate references like it is done in ApplicationCallTxn constructor
    txn.boxes = BoxReference.translate_box_references(
        txn.boxes, txn.foreign_apps, txn.index
    )


def getTxnsAfterResourceAllocation(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    txnsToAllocateTo: list[Transaction],
    additionalAddresses: list[str],
    senderAddr: str,
    params: SuggestedParams,
) -> list[Transaction]:
    consensusAppId = consensusConfig.consensusAppId
    xAlgoId = consensusConfig.xAlgoId

    # make copy of txns
    txns = txnsToAllocateTo.copy()
    appCallTxnIndex = len(txns) - 1

    # add xALGO asset and proposers box
    txns[appCallTxnIndex].foreign_assets = [xAlgoId]
    add_box_to_appcall(txns[appCallTxnIndex], (consensusAppId, "pr".encode()))

    # get all accounts we need to add
    uniqueAddresses = dict.fromkeys(additionalAddresses)
    uniqueAddresses |= dict.fromkeys(
        proposer.address for proposer in consensusState.proposersBalances
    )
    uniqueAddresses.pop(senderAddr, None)
    accounts = list(uniqueAddresses)

    # add accounts in groups of 4
    MAX_FOREIGN_ACCOUNT_PER_TXN = 4
    for i in range(0, len(accounts), MAX_FOREIGN_ACCOUNT_PER_TXN):
        # which txn to use and check to see if we need to add a dummy call
        if (i // MAX_FOREIGN_ACCOUNT_PER_TXN) == 0:
            txnIndex = appCallTxnIndex
        else:
            txns.insert(0, prepareDummyTransaction(consensusConfig, senderAddr, params))
            txnIndex = 0

        # add proposer accounts
        txns[txnIndex].accounts = accounts[i : i + 4]

    return txns


def getProposerIndex(consensusState: ConsensusState, proposerAddr: str) -> int:
    index = [p.address for p in consensusState.proposersBalances].index(proposerAddr)
    return index


def prepareImmediateStakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    receiverAddr: str,
    amount: int,
    minReceivedAmount: int,
    params: SuggestedParams,
    note: bytes | None = None,
) -> list[Transaction]:
    """
    Returns a group transaction to stake ALGO and get xALGO immediately.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param receiverAddr - account address to receive the xALGO at (typically the user)
    @param amount - amount of ALGO to send
    @param minReceivedAmount - min amount of xALGO expected to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param note - optional note to distinguish who is the minter (must pass to be eligible for revenue share)
    @returns Transaction[] stake transactions
    """
    consensusAppId = consensusConfig.consensusAppId

    sendAlgo = transferAlgoOrAsset(
        0,
        senderAddr,
        get_application_address(consensusAppId),
        amount,
        sp_fee(params, fee=0),
    )
    fee = 1000 * (3 + len(consensusState.proposersBalances))

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=consensusAppId,
        method=xAlgoABIContract.get_method_by_name("immediate_mint"),
        method_args=[
            TransactionWithSigner(sendAlgo, signer),
            receiverAddr,
            minReceivedAmount,
        ],
        sp=sp_fee(params, fee=fee),
        note=note,
    )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    return getTxnsAfterResourceAllocation(
        consensusConfig, consensusState, txns, [receiverAddr], senderAddr, params
    )


def prepareImmediateStakeAndDepositTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    pool: Pool,
    poolManagerAppId: int,
    senderAddr: str,
    receiverAddr: str,
    amount: int,
    minXAlgoReceivedAmount: int,
    params: SuggestedParams,
    note: bytes | None = None,
) -> list[Transaction]:
    """
    Returns a group transaction to stake ALGO and deposit the xALGO received.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param pool - pool application to deposit into
    @param poolManagerAppId - pool manager application
    @param senderAddr - account address for the sender
    @param receiverAddr - account address to receive the deposit (typically the user's deposit escrow or loan escrow)
    @param amount - amount of ALGO to send
    @param minXAlgoReceivedAmount - min amount of xALGO expected to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param note - optional note to distinguish who is the minter (must pass to be eligible for revenue share)
    @returns Transaction[] stake transactions
    """
    consensusAppId = consensusConfig.consensusAppId
    xAlgoId = consensusConfig.xAlgoId
    stakeAndDepositAppId = consensusConfig.stakeAndDepositAppId
    poolAppId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId

    if assetId != xAlgoId:
        raise ValueError("xAlgo pool not passed")

    sendAlgo = transferAlgoOrAsset(
        0,
        senderAddr,
        get_application_address(stakeAndDepositAppId),
        amount,
        sp_fee(params, fee=0),
    )
    fee = 1000 * (9 + len(consensusState.proposersBalances))

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=stakeAndDepositAppId,
        method=stakeAndDepositABIContract.get_method_by_name("stake_and_deposit"),
        method_args=[
            TransactionWithSigner(sendAlgo, signer),
            consensusAppId,
            poolAppId,
            poolManagerAppId,
            assetId,
            fAssetId,
            receiverAddr,
            minXAlgoReceivedAmount,
        ],
        sp=sp_fee(params, fee=fee),
        note=note,
    )

    txns = remove_signer_and_group(atc.build_group())

    # allocate resources, add accounts in groups of 4
    MAX_FOREIGN_ACCOUNT_PER_TXN = 4
    accounts = [proposer.address for proposer in consensusState.proposersBalances]
    for i in range(0, len(accounts), MAX_FOREIGN_ACCOUNT_PER_TXN):
        txns.insert(0, prepareDummyTransaction(consensusConfig, senderAddr, params))
        txns[0].accounts = accounts[i : i + 4]

    add_box_to_appcall(txns[0], (consensusAppId, "pr".encode()))
    return txns


def prepareDelayedStakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    receiverAddr: str,
    amount: int,
    nonce: bytes,
    params: SuggestedParams,
    includeBoxMinBalancePayment: bool = True,
    note: bytes | None = None,
) -> list[Transaction]:
    """
    Returns a group transaction to stake ALGO and get xALGO after 320 rounds.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param receiverAddr - account address to receive the xALGO at (typically the user)
    @param amount - amount of ALGO to send
    @param nonce - used to generate the delayed mint box (must be two bytes in length)
    @param params - suggested params for the transactions with the fees overwritten
    @param includeBoxMinBalancePayment - whether to include ALGO payment to app for box min balance
    @param note - optional note to distinguish who is the minter (must pass to be eligible for revenue share)
    @returns Transaction[] stake transactions
    """
    consensusAppId = consensusConfig.consensusAppId

    if len(nonce) != 2:
        raise ValueError("Nonce must be two bytes")
    # we rely on caller to check nonce is not already in use for sender address

    sendAlgo = transferAlgoOrAsset(
        0,
        senderAddr,
        get_application_address(consensusAppId),
        amount,
        sp_fee(params, fee=0),
    )
    fee = 1000 * (2 + len(consensusState.proposersBalances))

    atc = AtomicTransactionComposer()
    boxName = "dm".encode() + decode_address(senderAddr) + nonce

    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=consensusAppId,
        method=xAlgoABIContract.get_method_by_name("delayed_mint"),
        method_args=[TransactionWithSigner(sendAlgo, signer), receiverAddr, nonce],
        boxes=[(consensusAppId, boxName)],
        sp=sp_fee(params, fee=fee),
        note=note,
    )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    txns = getTxnsAfterResourceAllocation(
        consensusConfig, consensusState, txns, [], senderAddr, params
    )

    # add box min balance payment if specified
    if includeBoxMinBalancePayment:
        minBalance = 36100
        appAddr = get_application_address(consensusAppId)
        txns = [transferAlgoOrAsset(0, senderAddr, appAddr, minBalance, params)] + txns

    return txns


def prepareClaimDelayedStakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    minterAddr: str,
    receiverAddr: str,
    nonce: bytes,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to claim xALGO from delayed stake after 320 rounds.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param minterAddr - account address for the user who submitted the delayed stake
    @param receiverAddr - account address for the receiver of the xALGO
    @param nonce - what was used to generate the delayed mint box
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] stake transactions
    """
    consensusAppId = consensusConfig.consensusAppId

    atc = AtomicTransactionComposer()
    boxName = "dm".encode() + decode_address(minterAddr) + nonce

    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=consensusAppId,
        method=xAlgoABIContract.get_method_by_name("claim_delayed_mint"),
        method_args=[minterAddr, nonce],
        boxes=[(consensusAppId, boxName)],
        sp=sp_fee(params, fee=3000),
    )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    return getTxnsAfterResourceAllocation(
        consensusConfig, consensusState, txns, [receiverAddr], senderAddr, params
    )


def prepareUnstakeTransactions(
    consensusConfig: ConsensusConfig,
    consensusState: ConsensusState,
    senderAddr: str,
    receiverAddr: str,
    amount: int,
    minReceivedAmount: int,
    params: SuggestedParams,
    note: bytes | None = None,
) -> list[Transaction]:
    """
    Returns a group transaction to unstake xALGO and get ALGO.

    @param consensusConfig - consensus application and xALGO config
    @param consensusState - current state of the consensus application
    @param senderAddr - account address for the sender
    @param receiverAddr - account address to receive the xALGO at (typically the user)
    @param amount - amount of xALGO to send
    @param minReceivedAmount - min amount of ALGO expected to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param note - optional note to distinguish who is the burner (must pass to be eligible for revenue share)
    @returns Transaction[] unstake transactions
    """
    consensusAppId = consensusConfig.consensusAppId
    xAlgoId = consensusConfig.xAlgoId

    sendXAlgo = transferAlgoOrAsset(
        xAlgoId,
        senderAddr,
        get_application_address(consensusAppId),
        amount,
        sp_fee(params, fee=0),
    )
    fee = 1000 * (3 + len(consensusState.proposersBalances))

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=consensusAppId,
        method=xAlgoABIContract.get_method_by_name("burn"),
        method_args=[
            TransactionWithSigner(sendXAlgo, signer),
            receiverAddr,
            minReceivedAmount,
        ],
        sp=sp_fee(params, fee=fee),
        note=note,
    )

    # allocate resources
    txns = remove_signer_and_group(atc.build_group())
    return getTxnsAfterResourceAllocation(
        consensusConfig, consensusState, txns, [receiverAddr], senderAddr, params
    )
