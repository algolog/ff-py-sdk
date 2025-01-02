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
    prepareRepayLoanWithTxn,
)
from ffsdk.lending.v2.utils import userLoanInfo
from ffsdk.lending.v2.oracle import getOraclePrices
from ffsdk.lending.v2.opup import prefixWithOpUp
from ffsdk.mathlib import ONE_4_DP, ONE_14_DP
from ffsdk.state_utils import get_balances
from ffutils import user_loan_report, ask_sign_and_send
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Repay loan in escrow")
parser.add_argument("escrow_address")
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

# configure repay
loan_pools = list(loan_info.pools)
print(", ".join(['{}-{}'.format(i, market_by_id[b.poolAppId]) for i, b in enumerate(loan.borrows)]))
borrow_ask = input('Borrow market [0]: ')
borrow_ask = int(borrow_ask) if borrow_ask else 0
borrow_to_repay = loan.borrows[borrow_ask]
market = market_by_id[borrow_to_repay.poolAppId]
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

# ask amount
max_to_repay = borrow_to_repay.borrowBalance
repay_amount = max_to_repay

sender = USER_ACCOUNT.addr
assert user_address == sender
receiver = user_address

print("Preparing repay txns...")
print(f"sender: {user_address}")
print(f"receiver: {receiver}")
print(f"escrow: {escrow}")
print(f"repay_amount: {repay_amount:_}")
print(f"market: {market}")

# prepare txns
params = client.algod.suggested_params()

repay_txns = prepareRepayLoanWithTxn(
    loanAppId=loan_app_id,
    poolManagerAppId=client.pool_manager_app_id,
    userAddr=user_address,
    escrowAddr=escrow,
    receiverAddr=receiver,
    reserveAddr=client.reserve_address,
    pool=pool,
    repayAmount=repay_amount,
    isStable=False,
    params=params,
)

unsigned_txns = repay_txns


# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
