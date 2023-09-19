from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import LoanType, Account
from ffsdk.lending.v2.deposit import retrievePoolManagerInfo
from ffsdk.lending.v2.loan import (
    retrieveLoanInfo,
    retrieveLoanLocalState,
    prepareAddCollateralToLoan,
)
from ffsdk.lending.v2.utils import userLoanInfo
from ffsdk.lending.v2.oracle import getOraclePrices
from ffsdk.lending.v2.opup import prefixWithOpUp
from ffsdk.state_utils import get_balances
from ffsdk.transaction_utils import transferAlgoOrAsset
from ffutils import user_loan_report, ask_sign_and_send
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Optin loan escrow into collateral asset")
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

# configure optin
print("Markets:", *client.pools.keys())
market = input('Select market: ')
pool = client.pools[market]
escrow_holdings = get_balances(indexer, escrow)
if pool.fAssetId in escrow_holdings:
    raise ValueError(f"Escrow is already opted into {market}")

sender = USER_ACCOUNT.addr
assert user_address == sender

print("Preparing optin txns...")
print(f"market: {market}")
print(f"escrow: {escrow}")
print(f"sender: {user_address}")

# prepare txns
params = client.algod.suggested_params()

send_txn = transferAlgoOrAsset(0, sender, escrow, 100_000, params)

optin_txn = prepareAddCollateralToLoan(
    loan_app_id,
    client.pool_manager_app_id,
    user_address,
    escrow,
    pool,
    params,
)

unsigned_txns = [send_txn, optin_txn]

# add opup transactions to increase opcode budget
opup_budget = 0
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, unsigned_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
