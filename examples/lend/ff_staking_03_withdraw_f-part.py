from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lend.datatypes import Account
from ffsdk.lend.deposit import retrievePoolManagerInfo
from ffsdk.lend.deposit_staking import (
    retrieveDepositStakingInfo,
    retrieveUserDepositStakingLocalState,
    prepareWithdrawFromDepositStakingEscrow,
)
from ffsdk.lend.utils import (
    depositStakingProgramsInfo,
    userDepositStakingInfo,
)
from ffsdk.lend.formulae import calcWithdrawReturn
from ffsdk.lend.oracle import getOraclePrices
from ffsdk.lend.opup import prefixWithOpUp
from ffsdk.state_utils import get_balances
from ffutils import user_staking_report, ask_sign_and_send
from decimal import Decimal
from fractions import Fraction
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Withdraw from deposit staking escrow")
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

# configure withdraw
stakeIndex = 0
index_ask = input(f'Stake index [{stakeIndex}]: ')
if index_ask:
    stakeIndex = int(index_ask)

# select staking program by index
stakingProgram = udsi.stakingPrograms[stakeIndex]
market = market_by_id[stakingProgram.poolAppId]
pool = client.pools[market]
depositInterestIndex = pmi.pools[pool.appId].depositInterestIndex
user_holdings = get_balances(indexer, user_address)
escrow_holdings = get_balances(indexer, escrow)
escrow_f_holding = escrow_holdings[pool.fAssetId]
assert escrow_f_holding == stakingProgram.fAssetStakedAmount
print(f"market: {market}")
print(f"user_holding: {user_holdings[pool.assetId]:_}")
print(f"f-balance: {escrow_f_holding:_}")
print(f"f-staked: {stakingProgram.fAssetStakedAmount}")
# ask amount
max_part_to_withdraw = Fraction(1)
part_ask = input(f'Part of f-{market} to withraw [{max_part_to_withdraw}]: ').strip()
part_to_withdraw = Fraction(part_ask) if part_ask else max_part_to_withdraw
withdraw_amount = int(Decimal(part_to_withdraw.numerator * escrow_f_holding) / part_to_withdraw.denominator)
if withdraw_amount <= 0 or withdraw_amount > escrow_f_holding:
    raise ValueError(f"Bad withdraw amount: {withdraw_amount}")
calculated_return = calcWithdrawReturn(withdraw_amount, depositInterestIndex)

sender = USER_ACCOUNT.addr
assert user_address == sender
receiver = user_address

print("Preparing withdraw txns...")
print(f"escrow: {escrow}")
print(f"pool: {pool}")
print(f"sender: {user_address}")
print(f"reciever: {receiver}")
print(f"staking index: {stakeIndex}")
print(f"withdraw f-amount: {withdraw_amount:_}")
print(f"calculated return : {calculated_return:_}")

# prepare txns
params = client.algod.suggested_params()

withdraw_txn = prepareWithdrawFromDepositStakingEscrow(
    client.deposit_staking_app_id,
    pool,
    client.pool_manager_app_id,
    user_address,
    escrow,
    receiver,
    withdraw_amount,
    isfAssetAmount=True,
    remainDeposited=False,
    stakeIndex=stakeIndex,
    params=params,
)

unsigned_txns = [withdraw_txn]

# add opup transactions to increase opcode budget
opup_budget = 0
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, unsigned_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
