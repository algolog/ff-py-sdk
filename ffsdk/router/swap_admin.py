from algosdk.logic import get_application_address
from algosdk.transaction import Transaction, SuggestedParams, assign_group_id
from algosdk.atomic_transaction_composer import AtomicTransactionComposer
from .abi_contracts import routerABIContract
from ..transaction_utils import (
    signer,
    sp_fee,
    remove_signer_and_group,
    transferAlgoOrAsset,
)


def prepareEnableAssetToBeSwapped(
    appId: int,
    senderAddr: str,
    assetIds: list[int],
    params: SuggestedParams,
) -> list[Transaction]:
    # payment txn
    amount = len(assetIds) * int(0.1e6)
    paymentTxn = transferAlgoOrAsset(
        0, senderAddr, get_application_address(appId), amount, params
    )

    # opt in txn
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=senderAddr,
        signer=signer,
        app_id=appId,
        method=routerABIContract.get_method_by_name("opt_into_assets"),
        method_args=[assetIds],
        foreign_assets=assetIds,
        sp=sp_fee(params, fee=(1 + len(assetIds)) * 1000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return assign_group_id([paymentTxn, txns[0]])
