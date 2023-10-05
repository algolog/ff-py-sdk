from algosdk.v2client.indexer import IndexerClient
from algosdk.logic import get_application_address
from algosdk.transaction import SuggestedParams, Transaction
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from ..transaction_utils import (
    signer,
    sp_fee,
    remove_signer_and_group,
    transferAlgoOrAsset,
)
from ..config import ALGO_ASSET_ID
from ..state_utils import get_global_state, get_balances
from .abiContracts import xAlgoABIContract
from .datatypes import XAlgo, XAlgoInfo


def getXAlgoInfo(client: IndexerClient, xAlgo: XAlgo) -> XAlgoInfo:
    """
    Returns information regarding the given xAlgo application.

    @param client - Algorand client to query
    @param xAlgo - xAlgo to query about
    @returns DispenserInfo[] dispenser info
    """
    appId = xAlgo.appId
    xAlgoId = xAlgo.xAlgoId

    holdings = get_balances(client, get_application_address(appId))
    state = get_global_state(client, appId)

    timeDelay = state.get("time_delay", 0)
    commitEnd = state.get("commit_end", 0)
    fee = state.get("fee", 0)
    hasClaimedFee = bool(state.get("has_claimed_fee", 0))
    isMintingPaused = bool(state.get("is_minting_paused", 0))

    algoBalance = holdings.get(ALGO_ASSET_ID) - int(0.2e6)
    xAlgoCirculatingBalance = int(10e15) - holdings.get(xAlgoId)

    return XAlgoInfo(
        timeDelay,
        commitEnd,
        fee,
        hasClaimedFee,
        isMintingPaused,
        algoBalance,
        xAlgoCirculatingBalance,
    )


def prepareMintXAlgoTransactions(
    xAlgo: XAlgo,
    senderAddr: str,
    amount: int,
    minReceivedAmount: int,
    params: SuggestedParams,
    note: bytes | None,
) -> list[Transaction]:
    """
    Returns a group transaction to mint xALGO for ALGO.

    @param xAlgo - xAlgo application to mint xALGO from
    @param senderAddr - account address for the sender
    @param amount - amount of ALGO to send
    @param minReceivedAmount - min amount of xALGO expected to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param note - optional note to distinguish who is the minter (must pass to be eligible for revenue share)
    @returns Transaction[] mint transactions
    """
    appId = xAlgo.appId
    xAlgoId = xAlgo.xAlgoId

    sendAlgo = transferAlgoOrAsset(
        0, senderAddr, get_application_address(appId), amount, sp_fee(params, 0)
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=appId,
        method=xAlgoABIContract.get_method_by_name("mint"),
        method_args=[
            TransactionWithSigner(sendAlgo, signer),
            xAlgoId,
            minReceivedAmount,
        ],
        sp=sp_fee(params, fee=3000),
        note=note,
    )
    return remove_signer_and_group(atc.build_group())


def prepareBurnXAlgoTransactions(
    xAlgo: XAlgo,
    senderAddr: str,
    amount: int,
    minReceivedAmount: int,
    params: SuggestedParams,
    note: bytes | None,
) -> list[Transaction]:
    """
    Returns a group transaction to burn xALGO for ALGO.

    @param xAlgo - xAlgo application to mint xALGO from
    @param senderAddr - account address for the sender
    @param amount - amount of xALGO to send
    @param minReceivedAmount - min amount of ALGO expected to receive
    @param params - suggested params for the transactions with the fees overwritten
    @param note - optional note to distinguish who is the burner (must pass to be eligible for revenue share)
    @returns Transaction[] mint transactions
    """
    appId = xAlgo.appId
    xAlgoId = xAlgo.xAlgoId

    sendXAlgo = transferAlgoOrAsset(
        xAlgoId, senderAddr, get_application_address(appId), amount, sp_fee(params, 0)
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=appId,
        method=xAlgoABIContract.get_method_by_name("burn"),
        method_args=[
            TransactionWithSigner(sendXAlgo, signer),
            xAlgoId,
            minReceivedAmount,
        ],
        sp=sp_fee(params, fee=3000),
        note=note,
    )
    return remove_signer_and_group(atc.build_group())
