from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id, write_to_file
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import Account
from ffsdk.lending.v2.deposit import (
    retrievePoolManagerInfo,
    prepareDepositIntoPool,
)
from ffsdk.lending.v2.deposit_staking import (
    retrieveDepositStakingInfo,
    retrieveUserDepositStakingLocalState,
    prepareSyncStakeInDepositStakingEscrow,
)
from ffsdk.lending.v2.utils import (
    depositStakingProgramsInfo,
    userDepositStakingInfo,
)
from ffsdk.lending.v2.oracle import getOraclePrices
from ffsdk.lending.v2.opup import prefixWithOpUp
from ffsdk.state_utils import get_balances
from ffutils import user_staking_report, ask_sign_and_send
from decimal import Decimal
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Deposit into deposit staking escrow")
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
pool_by_asset = {pool.assetId: name for name, pool in client.pools.items()}

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

# configure deposit
stakeIndex = 0
index_ask = input(f'Stake index [{stakeIndex}]: ')
if index_ask:
    stakeIndex = int(index_ask)

# select staking program by index
stakingProgram = udsi.stakingPrograms[stakeIndex]
market = market_by_id[stakingProgram.poolAppId]
pool = client.pools[market]
fAssetId = stakingProgram.fAssetId
user_holdings = get_balances(indexer, user_address)
escrow_holdings = get_balances(indexer, escrow)

user_holding_unscaled = Decimal(user_holdings[pool.assetId]) / 10**pool.assetDecimals
print(f"market: {market}")
print(f"user_holding_unscaled: {user_holding_unscaled}")
print(f"f-staked: {stakingProgram.fAssetStakedAmount:_}")
if fAssetId not in escrow_holdings:
    raise ValueError(f"Escrow is not opted into fAsset {fAssetId} (f-{market})")

# ask amount
max_to_deposit = user_holding_unscaled
amount_ask = input(f'Amount of {market} to deposit [{max_to_deposit}]: ').strip()
deposit_amount_unscaled = Decimal(amount_ask) if amount_ask else max_to_deposit
deposit_amount = int(deposit_amount_unscaled * 10**pool.assetDecimals)

sender = USER_ACCOUNT.addr
assert user_address == sender

print("Preparing deposit txns...")
print(f"sender: {user_address}")
print(f"escrow: {escrow}")
print(f"staking index: {stakeIndex}")
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

sync_txn = prepareSyncStakeInDepositStakingEscrow(
    client.deposit_staking_app_id,
    pool,
    user_address,
    escrow,
    stakeIndex,
    params
)

unsigned_txns = deposit_txns + [sync_txn]

# add opup transactions to increase opcode budget
opup_budget = 0
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, unsigned_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)
#write_to_file(txn_group, '_ff_staking_deposit.txns')

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
