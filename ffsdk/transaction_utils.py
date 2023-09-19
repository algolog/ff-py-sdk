from copy import copy
from algosdk.atomic_transaction_composer import TransactionWithSigner, EmptySigner
from algosdk.encoding import decode_address, encode_as_bytes
from algosdk.logic import get_application_address
from algosdk.transaction import (
    SuggestedParams,
    Transaction,
    PaymentTxn,
    AssetTransferTxn,
)


signer = EmptySigner()


def sp_fee(sp: SuggestedParams, fee: int, flat_fee: bool = True) -> SuggestedParams:
    """
    Get a copy of suggested params but with a different fee.
    """
    sp = copy(sp)
    sp.flat_fee = flat_fee
    sp.fee = fee
    return sp


def remove_signer_and_group(
    txns_with_signer: list[TransactionWithSigner],
) -> list[Transaction]:
    res_txns: list[Transaction] = []
    for tws in txns_with_signer:
        txn = tws.txn
        txn.group = None
        res_txns.append(txn)
    return res_txns


def transferAlgoOrAsset(
    asset_id: int,
    sender: str,
    receiver: str,
    amount: int,
    params: SuggestedParams,
) -> Transaction:
    """
    Transfer algo or asset. 0 assetId indicates algo transfer, else asset transfer.
    """
    if asset_id != 0:
        return AssetTransferTxn(sender, params, receiver, amount, asset_id)
    else:
        return PaymentTxn(sender, params, receiver, amount)


def addEscrowNoteTransaction(
    userAddr: str,
    escrowAddr: str,
    appId: int,
    notePrefix: str,
    params: SuggestedParams,
) -> Transaction:
    note = encode_as_bytes(notePrefix) + decode_address(escrowAddr)
    return PaymentTxn(userAddr, params, get_application_address(appId), 0, note=note)


def removeEscrowNoteTransaction(
    escrowAddr: str,
    userAddr: str,
    notePrefix: str,
    params: SuggestedParams,
) -> Transaction:
    note = encode_as_bytes(notePrefix) + decode_address(escrowAddr)
    return PaymentTxn(
        escrowAddr, params, userAddr, 0, close_remainder_to=userAddr, note=note
    )
