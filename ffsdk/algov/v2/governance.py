import re
import json
from base64 import b64decode
from algosdk.v2client.indexer import IndexerClient
from algosdk.encoding import encode_address, decode_address
from algosdk.transaction import (
    LogicSigAccount,
    SuggestedParams,
    Transaction,
)
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk.logic import get_application_address
from .constants.abiContracts import abiDistributor
from ...state_utils import get_global_state, get_local_state_at_app
from ...transaction_utils import (
    signer,
    sp_fee,
    remove_signer_and_group,
    transferAlgoOrAsset,
    addEscrowNoteTransaction,
)
from ..common import Dispenser, Distributor
from .datatypes import (
    DistributorInfo,
    UserCommitmentInfo,
    EscrowGovernaceInfo,
    EscrowGovernanceStatus,
)


def getDistributorLogicSig(userAddr: str) -> LogicSigAccount:
    # fmt: off
    prefix = bytearray([
      7, 32, 1, 1, 128, 36, 70, 79, 76, 75, 83, 95, 70, 73, 78, 65, 78, 67, 69, 95,
      65, 76, 71, 79, 95, 76, 73, 81, 85, 73, 68, 95, 71, 79, 86, 69, 82, 78, 65, 78,
      67, 69, 72, 49, 22, 34, 9, 56, 16, 34, 18, 68, 49, 22, 34, 9, 56, 0, 128, 32,
    ])
    suffix = bytearray([
      18, 68, 49, 22, 34, 9, 56, 8, 20, 68, 49, 22, 34, 9, 56, 32, 50, 3, 18, 68,
      49, 22, 34, 9, 56, 9, 50, 3, 18, 68, 49, 22, 34, 9, 56, 21, 50, 3, 18, 68,
      34, 67,
    ])
    # fmt: on
    return LogicSigAccount(prefix + decode_address(userAddr) + suffix)


def getDistributorInfo(
    client: IndexerClient, distributor: Distributor
) -> DistributorInfo:
    """
    Returns information regarding the given liquid governance distributor.

    @param client - Algorand client to query
    @param distributor - distributor to query about
    @returns DistributorInfo[] distributor info
    """
    appId = distributor.appId
    state = get_global_state(client, appId)

    dispenserAppId = state.get("dispenser_app_id", 0)
    premintEnd = state.get("premint_end", 0)
    commitEnd = state.get("commit_end", 0)
    periodEnd = state.get("period_end", 0)
    fee = state.get("fee", 0)
    totalCommitment = state.get("total_commitment", 0)
    isBurningPaused = bool(state.get("is_burning_paused", 0))

    return DistributorInfo(
        dispenserAppId,
        premintEnd,
        commitEnd,
        periodEnd,
        fee,
        totalCommitment,
        isBurningPaused,
    )


def getUserLiquidGovernanceInfo(
    client: IndexerClient,
    distributor: Distributor,
    userAddr: str,
) -> UserCommitmentInfo:
    """
    Returns information regarding a user's liquid governance commitment.

    @param client - Algorand client to query
    @param distributor - distributor to query about
    @param userAddr - user address to get governance info about
    @returns UserCommitmentInfo user commitment info
    """
    appId = distributor.appId
    escrowAddr = getDistributorLogicSig(userAddr).address()

    # get user account local state
    state = get_local_state_at_app(client, appId, escrowAddr)
    if state is None:
        raise ValueError(f"Could not find user {userAddr} in liquid gov {appId}")

    # user local state
    canDelegate = bool(state.get("d"))
    premint = state.get("p", 0)
    commitment = state.get("c", 0)
    nonCommitment = state.get("n", 0)

    return UserCommitmentInfo(
        userAddr,
        canDelegate,
        premint,
        commitment,
        nonCommitment,
    )


def getEscrowGovernanceStatus(
    indexerClient: IndexerClient,
    userAddr: str,
    signUpAddr: str,
) -> EscrowGovernanceStatus:
    """
    Returns information regarding a user's escrow governance status.

    @param indexerClient - Algorand indexer client to query
    @param userAddr - user address to get governance info about
    @param signUpAddr - sign up address for the governance period
    @returns EscrowGovernanceStatus escrow governance status
    """
    escrowAddr = getDistributorLogicSig(userAddr).address()
    notePrefix = "af/gov"

    res = indexerClient.search_transactions(
        address=escrowAddr,
        address_role="sender",
        txn_type="pay",
        note_prefix=notePrefix.encode(),
    )
    account_info = indexerClient.account_info(escrowAddr)["account"]
    algoBalance = account_info["amount"]
    isOnline = account_info["status"] == "Online"

    for txn in res["transactions"]:
        payTxn = txn["inner-txns"][0] if txn["tx-type"] == "appl" else txn
        receiver: str = payTxn["payment-transaction"]["receiver"]
        if receiver == signUpAddr:
            note: str = b64decode(payTxn["note"]).decode()
            NOTE_SPECS_REGEX = re.compile(
                f"^{notePrefix}" + r"(?P<version>\d+):j(?P<jsonData>.*)$"
            )
            match = re.match(NOTE_SPECS_REGEX, note)

            if (match is None) or (not match.groups()):
                continue
            version, jsonData = match.groups()

            try:
                data = json.loads(jsonData)
                commitment = data.get("com", None) if isinstance(data, dict) else None
                if commitment is not None:
                    return EscrowGovernanceStatus(
                        balance=algoBalance,
                        isOnline=isOnline,
                        status=EscrowGovernaceInfo(
                            version=int(version),
                            commitment=int(commitment),
                            beneficiaryAddress=data.get("bnf", None),
                            xGovControlAddress=data.get("xGv", None),
                        ),
                    )
            except Exception as e:
                # raise e
                pass

    return EscrowGovernanceStatus(
        balance=algoBalance,
        isOnline=isOnline,
    )


def prepareMintTransactions(
    dispenser: Dispenser,
    distributor: Distributor,
    senderAddr: str,
    amount: int,
    ensureCommit: bool,
    params: SuggestedParams,
    note: bytes | None,
) -> list[Transaction]:
    """
    Returns a group transaction to mint gALGO for ALGO at a one-to-one rate.

    If you want to commit then MUST be paired with prepareCommitOrVoteTransaction
    as to send the required note to the signup address.

    @param dispenser - dispenser to mint gALGO from
    @param distributor - distributor that calls dispenser and to send ALGO to
    @param senderAddr - account address for the sender
    @param amount - amount of ALGO to send and gALGO to mint
    @param ensureCommit - whether to ensure in commitment period
    @param params - suggested params for the transactions with the fees overwritten
    @param note - optional note to distinguish who is the minter (must pass to be eligible for revenue share)
    @returns Transaction[] mint transactions
    """
    escrowAddr = getDistributorLogicSig(senderAddr).address()

    sendAlgo = transferAlgoOrAsset(0, senderAddr, escrowAddr, amount, sp_fee(params, 0))

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=distributor.appId,
        method=abiDistributor.get_method_by_name("mint"),
        method_args=[
            TransactionWithSigner(sendAlgo, signer),
            escrowAddr,
            dispenser.appId,
            dispenser.gAlgoId,
            ensureCommit,
        ],
        sp=sp_fee(params, fee=4000),
        note=note,
    )
    return remove_signer_and_group(atc.build_group())


def prepareUnmintPremintTransaction(
    distributor: Distributor,
    senderAddr: str,
    amount: int,
    params: SuggestedParams,
    note: bytes | None,
) -> list[Transaction]:
    """
    Returns a transaction to unmint pre-minted gALGO for ALGO at a one-to-one rate.
    Must be in commitment period. By unminting, you will lose your governance rewards.

    @param distributor - distributor that calls dispenser and to send ALGO to
    @param senderAddr - account address for the sender
    @param amount - amount of gALGO to unmint and ALGO to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param note - optional note to distinguish who is the unminter (must pass to be eligible for revenue share)
    @returns Transaction unmint pre-mint transaction
    """
    escrowAddr = getDistributorLogicSig(senderAddr).address()

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=distributor.appId,
        method=abiDistributor.get_method_by_name("unmint_premint"),
        method_args=[escrowAddr, amount],
        sp=sp_fee(params, fee=4000),
        note=note,
    )
    return remove_signer_and_group(atc.build_group())


def prepareRegisterEscrowOnlineTransaction(
    distributor: Distributor,
    senderAddr: str,
    voteKey: bytes,
    selectionKey: bytes,
    stateProofKey: bytes,
    voteFirstRound: int,
    voteLastRound: int,
    voteKeyDilution: int,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to register escrow online.

    @param distributor - distributor that has escrow
    @param senderAddr - account address for the sender
    @param voteKey - vote key
    @param selectionKey - selection key
    @param stateProofKey - state proof key
    @param voteFirstRound - vote first round
    @param voteLastRound - vote last round
    @param voteKeyDilution - vote key dilution
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction register online transaction
    """
    escrowAddr = getDistributorLogicSig(senderAddr).address()

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=distributor.appId,
        method=abiDistributor.get_method_by_name("register_online"),
        method_args=[
            escrowAddr,
            encode_address(voteKey),
            encode_address(selectionKey),
            stateProofKey,
            voteFirstRound,
            voteLastRound,
            voteKeyDilution,
        ],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareRegisterEscrowOfflineTransaction(
    distributor: Distributor,
    senderAddr: str,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to register escrow offline.

    @param distributor - distributor that has escrow
    @param senderAddr - account address for the sender
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction register offline transaction
    """
    escrowAddr = getDistributorLogicSig(senderAddr).address()

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=distributor.appId,
        method=abiDistributor.get_method_by_name("register_offline"),
        method_args=[escrowAddr],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareCommitOrVoteTransaction(
    distributor: Distributor,
    senderAddr: str,
    destAddr: str,
    note: str,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to commit or vote in governance.

    @param distributor - distributor that has escrow
    @param senderAddr - account address for the sender
    @param destAddr - destination address
    @param note - note to send
    @param params - suggested params the transactions with the fees overwritten
    @returns Transaction commit/vote transaction
    """
    escrowAddr = getDistributorLogicSig(senderAddr).address()

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=distributor.appId,
        method=abiDistributor.get_method_by_name("governance"),
        method_args=[escrowAddr, destAddr, note],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareBurnTransactions(
    dispenser: Dispenser,
    distributor: Distributor,
    senderAddr: str,
    amount: int,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to burn gALGO for ALGO at a one-to-one rate.
    Must be after period end.

    @param dispenser - dispenser to send gALGO to
    @param distributor - distributor that calls dispenser and to send ALGO to
    @param senderAddr - account address for the sender
    @param amount - amount of gALGO to send and ALGO to receive
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] burn transactions
    """
    sendgALGO = transferAlgoOrAsset(
        dispenser.gAlgoId,
        senderAddr,
        get_application_address(dispenser.appId),
        amount,
        sp_fee(params, fee=0),
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=distributor.appId,
        method=abiDistributor.get_method_by_name("burn"),
        method_args=[TransactionWithSigner(sendgALGO, signer), dispenser.appId],
        sp=sp_fee(params, fee=3000),
    )
    return remove_signer_and_group(atc.build_group())
