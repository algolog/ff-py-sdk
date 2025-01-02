from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import LoanType
from ffsdk.lending.v2.deposit import (
    retrievePoolManagerInfo,
    retrieveUserDepositsInfo,
    retrieveUserDepositsFullInfo,
)
from ffsdk.lending.v2.deposit_staking import (
    retrieveDepositStakingInfo,
    retrieveUserDepositStakingsLocalState,
)
from ffsdk.lending.v2.loan import (
    retrieveUserLoansInfo,
    getUserLoanAssets,
)
from ffsdk.lending.v2.utils import (
    depositStakingProgramsInfo,
    userDepositStakingInfo,
)
from ffsdk.lending.v2.oracle import getOraclePrices
from ffsdk.mathlib import ONE_4_DP, ONE_14_DP
from ffutils import user_deposit_report, user_staking_report, user_loan_report
import argparse


parser = argparse.ArgumentParser(
    description="Show report on account deposits and loans in FF protocol"
)
parser.add_argument("user_address")
parser.add_argument("--no-loans", action="store_true", help="Do not show loans info")
args = parser.parse_args()


algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "https://mainnet-idx.algonode.cloud")
client = FFMainnetClient(algod, indexer).lending

# retrieve general pools information and oracle prices
pmi = retrievePoolManagerInfo(client.indexer, client.pool_manager_app_id)
oracle_prices = getOraclePrices(client.indexer, client.oracle)
pool_by_id = {pool.appId: name for name, pool in client.pools.items()}
pool_by_asset = {pool.assetId: name for name, pool in client.pools.items()}
user_address = args.user_address
print(f"account: {user_address}")


# deposit staking report
udsls_list = retrieveUserDepositStakingsLocalState(
    client.indexer, client.deposit_staking_app_id, user_address
)
dsi = retrieveDepositStakingInfo(client.indexer, client.deposit_staking_app_id)
dspi = depositStakingProgramsInfo(dsi, pmi, client.pools, oracle_prices)

for udsi in (userDepositStakingInfo(udsls, pmi, dspi) for udsls in udsls_list):
    user_staking_report(udsi, client.pools)


# deposits report
userDepositsInfo = retrieveUserDepositsInfo(
    client.indexer, client.deposits_app_id, user_address
)
udfi_list = retrieveUserDepositsFullInfo(
    client.indexer,
    client.pool_manager_app_id,
    client.deposits_app_id,
    client.pools,
    client.oracle,
    userDepositsInfo,
)
for udfi in udfi_list:
    user_deposit_report(udfi, client.pools)

# loans report
loan_types = [] if args.no_loans else LoanType

for ltype in loan_types:
    userLoansInfo = retrieveUserLoansInfo(
        client.indexer,
        client.loans[ltype],
        client.pool_manager_app_id,
        client.oracle,
        user_address,
    )
    for loan in userLoansInfo:
        user_loan_report(loan, ltype, client.pools)
