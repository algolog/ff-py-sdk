from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import LoanType, Account
from ffsdk.lending.v2.deposit import retrievePoolManagerInfo
from ffsdk.lending.v2.loan import (
    retrieveLoanInfo,
    retrieveLoanLocalState,
    getUserLoanAssets,
    getMaxReduceCollateralForBorrowUtilisationRatio,
    prepareReduceCollateralFromLoan,
)
from ffsdk.lending.v2.utils import userLoanInfo
from ffsdk.lending.v2.formulae import calcWithdrawReturn
from ffsdk.lending.v2.oracle import getOraclePrices
from ffsdk.lending.v2.opup import prefixWithOpUp
from ffsdk.lending.v2.mathlib import ONE_4_DP
from ffsdk.state_utils import get_balances
from ffutils import user_loan_report, ask_sign_and_send
from decimal import Decimal
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Remove collateral from loan escrow")
parser.add_argument("escrow_address")
parser.add_argument("-m", "--max-utilization", type=float, default=0.8, help='Max allowed utilization after removal')
args = parser.parse_args()

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "https://mainnet-idx.algonode.cloud")
client = FFMainnetClient(algod, indexer).lending

# retrieve general pools information and oracle prices
pmi = retrievePoolManagerInfo(client.indexer, client.pool_manager_app_id)
oracle_prices = getOraclePrices(client.indexer, client.oracle)
market_by_id = {pool.appId: name for name, pool in client.pools.items()}
pool_by_asset = {pool.assetId: name for name, pool in client.pools.items()}

escrow = args.escrow_address

# deduce loan type by checking escrow local state at loan apps
for ltype in LoanType:
    try:
        local_state = retrieveLoanLocalState(client.indexer, client.loans[ltype], escrow)
        break
    except LookupError:
        pass

# fetch loan info
loan_app_id = client.loans[ltype]
loan_info = retrieveLoanInfo(client.indexer, loan_app_id)
loan = userLoanInfo(local_state, pmi, loan_info, oracle_prices)
assert loan.escrowAddress == escrow
user_address = loan.userAddress

# print report
print(f"addres: {user_address}")
user_loan_report(loan, ltype, client.pools)

# configure removal of collateral
print(", ".join(['{}-{}'.format(i, market_by_id[c.poolAppId]) for i, c in enumerate(loan.collaterals)]))
collateral_ask = input('Remove f-collateral [0]: ')
collateral_ask = int(collateral_ask) if collateral_ask else 0
collateral_selected = loan.collaterals[collateral_ask]
market = market_by_id[collateral_selected.poolAppId]
pool = client.pools[market]
depositInterestIndex = pmi.pools[pool.appId].depositInterestIndex
fAssetId = pool.fAssetId
user_holdings = get_balances(indexer, user_address)
escrow_holdings = get_balances(indexer, escrow)
lpAssets, baseAssetIds = getUserLoanAssets(client.pools, loan)
escrow_f_holding = escrow_holdings[fAssetId]
assert escrow_f_holding == collateral_selected.fAssetBalance

user_holding = user_holdings[pool.assetId]
print(f"user_holding: {user_holding:_}")
print(f"market: {market}")
print(f"escrow_f-holding: {escrow_f_holding:_}")

# ask amount
targetBorrowUtilisationRatio = int(args.max_utilization * ONE_4_DP)
max_to_remove = getMaxReduceCollateralForBorrowUtilisationRatio(loan, collateral_selected.poolAppId, targetBorrowUtilisationRatio)

if escrow_f_holding:
    max_part_to_remove = Decimal(max_to_remove) / escrow_f_holding
else:
    max_part_to_remove = 0
part_ask = input(f'Part of f-{market} collateral to remove [{max_part_to_remove:.2f}]: ').strip()
part_to_remove = Decimal(part_ask) if part_ask else max_part_to_remove
remove_amount = int(escrow_f_holding * part_to_remove)
if remove_amount <= 0 or remove_amount > escrow_f_holding:
    raise ValueError(f"Bad remove amount: {remove_amount}")
if remove_amount > max_to_remove:
    raise ValueError(f"WARNING: remove {remove_amount} is more than allowed for max utilization {max_to_remove}!")
calculated_return = calcWithdrawReturn(remove_amount, depositInterestIndex)

sender = USER_ACCOUNT.addr
assert user_address == sender
receiver = user_address

print("Preparing remove collateral txns...")
print(f"sender: {user_address}")
print(f"receiver: {receiver}")
print(f"escrow: {escrow}")
print(f"market: {market}")
print(f"remove_f-amount: {remove_amount:_}")
print(f"calculated return : {calculated_return:_}")

# prepare txns
params = client.algod.suggested_params()

remove_txns = prepareReduceCollateralFromLoan(
    loanAppId=loan_app_id,
    poolManagerAppId=client.pool_manager_app_id,
    userAddr=user_address,
    escrowAddr=escrow,
    receiverAddr=receiver,
    pool=pool,
    oracle=client.oracle,
    lpAssets=lpAssets,
    baseAssetIds=baseAssetIds,
    amount=remove_amount,
    isfAssetAmount=True,
    params=params,
)

unsigned_txns = remove_txns

# add opup transactions to increase opcode budget
opup_budget = 4
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, unsigned_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
