from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lend.datatypes import Account
from ffsdk.lend.deposit import retrievePoolManagerInfo
from ffsdk.lend.deposit_staking import (
    retrieveDepositStakingInfo,
    retrieveUserDepositStakingLocalState,
    prepareClaimRewardsOfDepositStakingEscrow,
)
from ffsdk.lend.utils import (
    depositStakingProgramsInfo,
    userDepositStakingInfo,
)
from ffsdk.lend.oracle import getOraclePrices
from ffsdk.lend.opup import prefixWithOpUp
from ffutils import user_staking_report, ask_sign_and_send
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Claim deposit staking rewards")
parser.add_argument("escrow_address")
args = parser.parse_args()

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "https://mainnet-idx.algonode.cloud")
client = FFMainnetClient(algod, indexer).lending

# retrieve general pool information and oracle prices
pmi = retrievePoolManagerInfo(client.indexer, client.pool_manager_app_id)
oracle_prices = getOraclePrices(client.indexer, client.oracle)
market_by_id = {pool.appId: name for name, pool in client.pools.items()}

# deposit staking info
dsi = retrieveDepositStakingInfo(client.indexer, client.deposit_staking_app_id)
dspi = depositStakingProgramsInfo(dsi, pmi, client.pools, oracle_prices)

escrow = args.escrow_address
udsls = retrieveUserDepositStakingLocalState(client.indexer, client.deposit_staking_app_id, escrow)
udsi = userDepositStakingInfo(udsls, pmi, dspi)
assert udsi.escrowAddress == escrow
user_address = udsi.userAddress

# print report
print(f"addres: {user_address}")
user_staking_report(udsi, client.pools)

# configure claim
stakeIndex = 0
index_ask = input(f'Stake index [{stakeIndex}]: ')
if index_ask:
    stakeIndex = int(index_ask)

# select staking program by index
stakingProgram = udsi.stakingPrograms[stakeIndex]
market = market_by_id[stakingProgram.poolAppId]
pool = client.pools[market]
rewards_amount = {r.rewardAssetId: r.unclaimedReward for r in stakingProgram.rewards}
rewardAssetIds = [r.rewardAssetId for r in stakingProgram.rewards]

sender = USER_ACCOUNT.addr
receiver = user_address
assert user_address == sender

print("Preparing claim txns...")
print(f"market: {market}")
print(f"unclaimed rewards: {rewards_amount}")
print(f"escrow: {escrow}")
print(f"sender: {user_address}")
print(f"reciever: {receiver}")
print(f"staking index: {stakeIndex}")

# prepare txns
params = client.algod.suggested_params()

claim_txns = prepareClaimRewardsOfDepositStakingEscrow(
    client.deposit_staking_app_id,
    user_address,
    escrow,
    receiver,
    stakeIndex,
    rewardAssetIds,
    params
)

unsigned_txns = claim_txns

# add opup transactions to increase opcode budget
opup_budget = 0
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, unsigned_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
