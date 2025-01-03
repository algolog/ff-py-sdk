from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo, get_balances
from ffsdk.lending.v2.datatypes import Account
from ffsdk.lending.v2.opup import prefixWithOpUp
from ffsdk.xalgo.consensus import (
    getConsensusState,
    prepareImmediateStakeTransactions,
)
from ffsdk.xalgo.formulae import convertAlgoToXAlgoWhenImmediate
from ffutils import ask_sign_and_send
from decimal import Decimal

USER_ACCOUNT = Account(addr="", sk="")

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "")

# get xalgo subclient and fetch consensus state
ff_client = FFMainnetClient(algod, indexer)
client = ff_client.xalgo
consensus_state = getConsensusState(client.algod, client.consensus_config)

# get user balances and ask stake amount
DECIMALS = 6
BALANCE_PAD = 500_000
sender = USER_ACCOUNT.addr
account_info = client.algod.account_info(sender)

user_balance = account_info["amount"]
print(f"User ALGO balance: {user_balance / 10**DECIMALS}")
max_stake = max(0, user_balance - account_info["min-balance"] - BALANCE_PAD)
max_stake_unscaled = Decimal(max_stake) / 10**DECIMALS

amount_ask = input(f"Amount of ALGO to stake [{max_stake_unscaled}]: ").strip()
stake_amount_unscaled = Decimal(amount_ask) if amount_ask else max_stake_unscaled
stake_amount = int(stake_amount_unscaled * 10**DECIMALS)
assert stake_amount > 0
calculated_return = convertAlgoToXAlgoWhenImmediate(stake_amount, consensus_state)
min_to_receive = (
    calculated_return * 9999 // 10000
)  # asking 0.01% less to prevent txn failure
receiver = sender

print("Preparing stake txns...")
print(f"sender: {sender}")
print(f"receiver: {receiver}")
print(f"amount of ALGO to stake: {stake_amount:_}")
print(f"calculated xALGO return: {calculated_return:_}")
print(f"minimal xALGO amount: {min_to_receive:_}")

# prepare stake transactions
params = client.algod.suggested_params()
txns = prepareImmediateStakeTransactions(
    client.consensus_config,
    consensus_state,
    sender,
    receiver,
    stake_amount,
    min_to_receive,
    params,
    note=None,
)

opup_budget = 1
print(f"opup budget: {opup_budget}")
txns = prefixWithOpUp(ff_client.lending.opup, sender, txns, opup_budget, params)

txn_group = assign_group_id(txns)
ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk, simulate=True)
