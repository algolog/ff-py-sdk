from algosdk.transaction import Transaction, SuggestedParams, ApplicationNoOpTxn
from algosdk.encoding import encode_as_bytes
from .datatypes import OpUp
from ...transaction_utils import sp_fee


def prefixWithOpUp(
    opup: OpUp,
    userAddr: str,
    transactions: Transaction | list[Transaction],
    numInnerTransactions: int,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Given a transaction or transaction group, prefixes it with appl call to increase opcode budget and returns the new
    transaction group.
    A lot of the lending operations require additional opcode cost so use this to increase the budget.

    @param opup - opup applications
    @param userAddr - account address for the user
    @param transactions - transaction(s) to prefix opup to
    @param numInnerTransactions - number of inner transactions to issue (remaining opcode is 691 + 689 * num.inner.txns)
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] transaction group with opup prefixed
    """

    if not isinstance(numInnerTransactions, int) or numInnerTransactions > 256:
        raise ValueError("Invalid number of inner transactions")

    callerAppId = opup.callerAppId
    baseAppId = opup.baseAppId

    fee = (numInnerTransactions + 1) * 1000
    prefix = ApplicationNoOpTxn(
        userAddr,
        sp_fee(params, fee, flat_fee=True),
        callerAppId,
        app_args=[encode_as_bytes(numInnerTransactions)],
        accounts=None,
        foreign_apps=[baseAppId],
    )

    if isinstance(transactions, list):
        txns = transactions
    else:
        txns = [transactions]

    txns = [prefix] + txns
    # clear group
    for t in txns:
        t.group = None

    return txns
