from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lend.datatypes import LoanType, Account
from ffsdk.lend.deposit import (
    retrievePoolManagerInfo,
    prepareDepositIntoPool,
)
from ffsdk.lend.loan import (
    retrieveLoanInfo,
    retrieveLoanLocalState,
    prepareSyncCollateralInLoan,

)
from ffsdk.lend.utils import userLoanInfo
from ffsdk.lend.oracle import getOraclePrices
from ffsdk.lend.opup import prefixWithOpUp
from ffsdk.state_utils import get_balances
from ffutils import user_loan_report, ask_sign_and_send
from decimal import Decimal
import argparse

USER_ACCOUNT = Account(addr="", sk="")
MIN_ALGO_BALANCE = Decimal("100")

parser = argparse.ArgumentParser(description="Deposit collateral to loan escrow")
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
user_loan_report(loan, ltype, client.lending_config)

# configure deposit
print(", ".join(['{}-{}'.format(i, market_by_id[c.poolAppId]) for i, c in enumerate(loan.collaterals)]))
default_collateral = 0
collateral_ask = input(f'Deposit market [{default_collateral}]: ')
collateral_ask = int(collateral_ask) if collateral_ask else default_collateral
collateral_to_deposit = loan.collaterals[int(collateral_ask)]
market = market_by_id[collateral_to_deposit.poolAppId]
pool = client.pools[market]
fAssetId = pool.fAssetId
user_holdings = get_balances(indexer, user_address)
escrow_holdings = get_balances(indexer, escrow)

user_holding_unscaled = Decimal(user_holdings[pool.assetId]) / 10**pool.assetDecimals
print(f"market: {market}")
print(f"user_holding_unscaled: {user_holding_unscaled}")
if fAssetId not in escrow_holdings:
    raise ValueError(f"Escrow is not opted into fAsset {fAssetId} (f-{market})")

# ask amount
max_to_deposit = user_holding_unscaled
if market == "ALGO":
    max_to_deposit = max(0, user_holding_unscaled - MIN_ALGO_BALANCE)
amount_ask = input(f'Amount of {market} to deposit [{max_to_deposit}]: ').strip()
deposit_amount_unscaled = Decimal(amount_ask) if amount_ask else max_to_deposit
deposit_amount = int(deposit_amount_unscaled * 10**pool.assetDecimals)

sender = USER_ACCOUNT.addr
assert user_address == sender

print("Preparing deposit txns...")
print(f"sender: {user_address}")
print(f"escrow: {escrow}")
print(f"market: {market}")
print(f"amount: {deposit_amount:_}")

# prepare txns
params = client.algod.suggested_params()

deposit_txns = prepareDepositIntoPool(
    pool,
    client.pool_manager_app_id,
    user_address,
    escrow,
    deposit_amount,
    params,
)

sync_txns = prepareSyncCollateralInLoan(
    loan_app_id,
    client.pool_manager_app_id,
    user_address,
    escrow,
    pool,
    client.oracle,
    params,
)

unsigned_txns = deposit_txns + sync_txns

# add opup transactions to increase opcode budget
opup_budget = 0
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, unsigned_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
