from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import Account
from ffsdk.lending.v2.deposit import retrievePoolManagerInfo, prepareWithdrawFromPool
from ffsdk.lending.v2.oracle import getOraclePrices
from ffsdk.lending.v2.opup import prefixWithOpUp
from ffsdk.lending.v2.formulae import calcWithdrawReturn
from ffsdk.state_utils import get_balances
from ffutils import ask_sign_and_send
from fractions import Fraction
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(description="Burn f-asset to asset")
parser.add_argument("pool_name", help="Market name (ALGO, USDC, etc.)")
parser.add_argument("part_to_burn", nargs="?", type=Fraction, default="1", help="Fraction of f-asset balance to burn")
args = parser.parse_args()

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "https://mainnet-idx.algonode.cloud")
client = FFMainnetClient(algod, indexer).lending

# retrieve general pool information and oracle prices
pmi = retrievePoolManagerInfo(client.indexer, client.pool_manager_app_id)
oracle_prices = getOraclePrices(client.indexer, client.oracle)

# configure burn
pool = client.pools[args.pool_name]
pool_info = pmi.pools[pool.appId]
depositInterestIndex = pool_info.depositInterestIndex

sender = USER_ACCOUNT.addr
fAssetId = pool.fAssetId
user_holdings = get_balances(indexer, sender)
user_holding = user_holdings[fAssetId]
part_to_burn = args.part_to_burn
burn_amount = (user_holding * part_to_burn.numerator) // part_to_burn.denominator

# show burn info
print(f"Market name: {args.pool_name}")
print(f"fAssetId: {fAssetId}")
print(f"User f-asset balance: {user_holding:_}")
print(f"Part to burn: {part_to_burn}")
print(f"Burn amount: {burn_amount:_}")

# calculate receive amount
receivedAssetAmount = 0  # set to zero in call for dynamic return
calculated_return = calcWithdrawReturn(burn_amount, depositInterestIndex)
print(f"Asking to receive (zero = dynamic): {receivedAssetAmount:_}")
print(f"Calculated return: {calculated_return:_}")

# prepare txns
params = client.algod.suggested_params()

burn_txns = prepareWithdrawFromPool(
    pool,
    client.pool_manager_app_id,
    sender,
    sender,
    burn_amount,
    receivedAssetAmount,
    params,
)

# add opup transactions to increase opcode budget
opup_budget = 1
print(f"opup budget: {opup_budget}")
unsigned_txns = prefixWithOpUp(client.opup, sender, burn_txns, opup_budget, params)

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
