from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo, get_balances
from ffsdk.lending.v2.datatypes import Account
from ffsdk.xalgo.consensus import (
    getConsensusState,
    prepareUnstakeTransactions,
)
from ffsdk.xalgo.formulae import convertXAlgoToAlgo
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

# get user balances and ask unstake amount
DECIMALS = 6
sender = USER_ACCOUNT.addr
account_info = client.algod.account_info(sender)
user_balances = {asset["asset-id"]: asset["amount"] for asset in account_info["assets"]}

user_holding = user_balances[client.consensus_config.xAlgoId]
user_holding_unscaled = Decimal(user_holding) / 10**DECIMALS

amount_ask = input(f"Amount of xALGO to unstake [{user_holding_unscaled}]: ").strip()
burn_amount_unscaled = Decimal(amount_ask) if amount_ask else user_holding_unscaled
burn_amount = int(burn_amount_unscaled * 10**DECIMALS)
assert burn_amount > 0
min_to_receive = convertXAlgoToAlgo(burn_amount, consensus_state)

print("Preparing unstake txns...")
print(f"sender: {sender}")
print(f"amount of xALGO to unstake: {burn_amount/10**DECIMALS}")
print(f"calculated ALGO return: {min_to_receive/10**DECIMALS}")

# prepare unstake transactions
params = client.algod.suggested_params()
txns = prepareUnstakeTransactions(
    client.consensus_config,
    consensus_state,
    sender,
    burn_amount,
    min_to_receive,
    params,
    note=None,
)

txn_group = assign_group_id(txns)
ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk, simulate=True)
