from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lend.datatypes import LoanType, Account
from ffsdk.lend.deposit import retrievePoolManagerInfo
from ffsdk.lend.loan import (
    retrieveLoanInfo,
    retrieveLoanLocalState,
    getUserLoanAssets,
    getMaxBorrowForBorrowUtilisationRatio,
    prepareBorrowFromLoan,
)
from ffsdk.lend.utils import userLoanInfo
from ffsdk.lend.formulae import calcWithdrawReturn
from ffsdk.lend.oracle import getOraclePrices
from ffsdk.lend.opup import prefixWithOpUp
from ffsdk.mathlib import ONE_4_DP, ONE_14_DP
from ffsdk.state_utils import get_balances
from ffutils import user_loan_report, ask_sign_and_send
from decimal import Decimal
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Borrow from loan escrow")
parser.add_argument("escrow_address")
parser.add_argument("-m", "--max-utilization", type=float, default=0.75, help='Max allowed utilization after borrow')
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
print(f"user address: {user_address}")
user_loan_report(loan, ltype, client.lending_config)

# configure borrow
loan_pools = list(loan_info.pools)
print(", ".join(['{}-{}'.format(i, market_by_id[pid]) for i, pid in enumerate(loan_pools)]))
market_ask = input('Borrow market [0]: ')
if market_ask in client.pools:
    market = market_ask
else:
    market_ask = int(market_ask) if market_ask else 0
    market = market_by_id[loan_pools[market_ask]]
pool = client.pools[market]
pool_loan_info = loan_info.pools[pool.appId]
depositInterestIndex = pmi.pools[pool.appId].depositInterestIndex
borrow_apy = pmi.pools[pool.appId].variableBorrowInterestYield / ONE_14_DP
asset_price = oracle_prices[pool.assetId].price
user_holdings = get_balances(indexer, user_address)
escrow_holdings = get_balances(indexer, escrow)
lpAssets, baseAssetIds = getUserLoanAssets(client.pools, loan)
if pool.assetId not in user_holdings:
    raise ValueError(f'User is not opted into {pool.AssetId} ({market})')

user_holding_unscaled = user_holdings[pool.assetId] / 10**pool.assetDecimals
print(f"market: {market}")
print(f"borrow APY: {borrow_apy:.2f}%")
print(f"user_holding_unscaled: {user_holding_unscaled:}")
print(f"target utilization: {args.max_utilization*100:g}%")

# ask amount
targetBorrowUtilisationRatio = int(args.max_utilization * ONE_4_DP)
max_to_borrow = getMaxBorrowForBorrowUtilisationRatio(
    loan,
    asset_price,
    pool_loan_info.borrowFactor,
    targetBorrowUtilisationRatio
)

max_to_borrow_unscaled = Decimal(max_to_borrow) / 10**pool.assetDecimals
borrow_ask = input(f'Borrow amount [{max_to_borrow_unscaled:}]: ').strip()
if borrow_ask:
    borrow_amount_unscaled = Decimal(borrow_ask)
else:
    borrow_amount_unscaled = max_to_borrow_unscaled

borrow_amount = int(borrow_amount_unscaled * 10**pool.assetDecimals)

if borrow_amount <= 0:
    raise ValueError(f"Bad borrow amount: {borrow_amount}")
if borrow_amount > max_to_borrow:
    raise ValueError(f"WARNING: borrow {borrow_amount} is more than allowed for max utilization {max_to_borrow}!")
borrow_value = borrow_amount * asset_price / ONE_14_DP
print(f"borrow value: {borrow_value:.2f}")

sender = USER_ACCOUNT.addr
assert user_address == sender
receiver = user_address

print("Preparing borrow txns...")
print(f"sender: {user_address}")
print(f"receiver: {receiver}")
print(f"escrow: {escrow}")
print(f"borrow_amount: {borrow_amount:_}")
print(f"market: {market}")

# prepare txns
params = client.algod.suggested_params()

borrow_txns = prepareBorrowFromLoan(
    loanAppId=loan_app_id,
    poolManagerAppId=client.pool_manager_app_id,
    userAddr=user_address,
    escrowAddr=escrow,
    receiverAddr=receiver,
    pool=pool,
    oracle=client.oracle,
    lpAssets=lpAssets,
    baseAssetIds=baseAssetIds,
    borrowAmount=borrow_amount,
    maxStableRate=0,  # if zero then variable borrow
    params=params,
)

unsigned_txns = borrow_txns

# add opup transactions to increase opcode budget
opup_budget = 4
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, unsigned_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
