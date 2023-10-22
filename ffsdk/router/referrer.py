from algosdk.encoding import decode_address, msgpack_encode
from algosdk.transaction import (
    LogicSigAccount,
    SuggestedParams,
    Transaction,
    assign_group_id,
)
from ..transaction_utils import sp_fee, transferAlgoOrAsset
from .datatypes import ReferrerTransaction, ReferrerGroupTransaction


def getReferrerLogicSig(referrerAddr: str) -> LogicSigAccount:
    # fmt: off
    prefix = bytearray([
        9, 32, 3, 1, 4, 0, 128, 12, 70, 79, 76, 75, 83, 95, 82, 79, 85, 84, 69, 82, 72, 49, 1, 36, 18, 68, 49, 32, 50, 3,
        18, 68, 49, 9, 50, 3, 18, 68, 49, 21, 50, 3, 18, 68, 49, 16, 34, 18, 49, 16, 35, 18, 17, 68, 49, 16, 35, 18, 49, 20,
        49, 0, 18, 16, 64, 0, 53, 49, 16, 35, 18, 64, 0, 41, 49, 7, 128, 32,
    ])
    suffix = bytearray([
        18, 68, 66, 0, 79, 49, 20, 66, 255, 212, 49, 22, 34, 9, 56, 16, 34, 18, 68, 49, 22, 34, 9, 56, 0, 49, 0, 19, 68, 49,
        22, 34, 9, 56, 7, 49, 0, 18, 68, 49, 22, 34, 9, 56, 8, 50, 1, 18, 68, 49, 22, 34, 9, 56, 32, 50, 3, 18, 68, 49, 22,
        34, 9, 56, 9, 50, 3, 18, 68, 49, 22, 34, 9, 56, 21, 50, 3, 18, 68, 49, 18, 36, 18, 68, 34, 67,
    ])
    # fmt: on
    return LogicSigAccount(prefix + decode_address(referrerAddr) + suffix)


def buildReferrerGroupTransaction(
    txns: list[Transaction], lsig: LogicSigAccount
) -> ReferrerGroupTransaction:
    return [
        ReferrerTransaction(
            msgpack_encode(txn),
            msgpack_encode(lsig) if txn.sender == lsig.address() else None,
        )
        for txn in assign_group_id(txns)
    ]


def prepareReferrerOptIntoAsset(
    senderAddr: str,
    referrerAddr: str,
    assetId: int,
    params: SuggestedParams,
) -> ReferrerGroupTransaction:
    lsig = getReferrerLogicSig(referrerAddr)

    # generate transactions
    MIN_BALANCE = int(0.1e6)
    minBalancePayment = transferAlgoOrAsset(
        0, senderAddr, lsig.address(), MIN_BALANCE, sp_fee(params, fee=2000)
    )
    assetOptIn = transferAlgoOrAsset(
        assetId, lsig.address(), lsig.address(), 0, sp_fee(params, fee=0)
    )

    # group, encode and attach lsig
    return buildReferrerGroupTransaction([minBalancePayment, assetOptIn], lsig)


def prepareClaimReferrerFees(
    senderAddr: str,
    referrerAddr: str,
    assetId: int,
    amount: int,
    params: SuggestedParams,
) -> ReferrerGroupTransaction:
    lsig = getReferrerLogicSig(referrerAddr)

    # generate transactions
    groupFeePayment = transferAlgoOrAsset(
        0, senderAddr, senderAddr, 0, sp_fee(params, 2000)
    )
    claim = transferAlgoOrAsset(
        assetId, lsig.address(), referrerAddr, amount, sp_fee(params, 0)
    )

    # group, encode and attach lsig
    return buildReferrerGroupTransaction([groupFeePayment, claim], lsig)
