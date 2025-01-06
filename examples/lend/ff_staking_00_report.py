from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lend.deposit import retrievePoolManagerInfo
from ffsdk.lend.deposit_staking import (
    retrieveDepositStakingInfo,
    retrieveUserDepositStakingsLocalState,
)
from ffsdk.lend.utils import (
    depositStakingProgramsInfo,
    userDepositStakingInfo,
)
from ffsdk.lend.oracle import getOraclePrices
from ffutils import user_staking_report
import argparse


parser = argparse.ArgumentParser(description="Show report of account staking deposits")
parser.add_argument("user_address")
args = parser.parse_args()

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "https://mainnet-idx.algonode.cloud")
client = FFMainnetClient(algod, indexer).lending

# retrieve general pools information and oracle prices
pmi = retrievePoolManagerInfo(client.indexer, client.pool_manager_app_id)
oracle_prices = getOraclePrices(client.indexer, client.oracle)
user_address = args.user_address
print(f"account: {user_address}")

# user deposit staking report
udsls_list = retrieveUserDepositStakingsLocalState(
    client.indexer, client.deposit_staking_app_id, user_address
)
dsi = retrieveDepositStakingInfo(client.indexer, client.deposit_staking_app_id)
dspi = depositStakingProgramsInfo(dsi, pmi, client.pools, oracle_prices)

for udsi in (userDepositStakingInfo(udsls, pmi, dspi) for udsls in udsls_list):
    user_staking_report(udsi, client.pools)
