from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import Account
from ffsdk.algo_liquid_governance.common import govDispenser, getDispenserInfo
from ffsdk.algo_liquid_governance.v2.governance import getDistributorInfo, prepareBurnTransactions
from ffsdk.state_utils import get_balances
from ffutils import ask_sign_and_send
from datetime import datetime

USER_ACCOUNT = Account(addr="", sk="")

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "")

# FolksFinance client
ff_client = FFMainnetClient(algod, indexer)
client = ff_client.algo_liquid_governance

# general info and checks of distributor and dispenser
distributor = client.distributor
distributor_info = getDistributorInfo(client.indexer, distributor)
if distributor_info.dispenserAppId != govDispenser.appId:
    raise ValueError("Dispenser appId mismatch")

dispenser_info = getDispenserInfo(client.indexer, govDispenser)
if distributor.appId not in dispenser_info.distributorAppIds:
    print(
        f"WARNING: distributor {distributor.appId} is not listed in dispenser {dispenser_info.distributorAppIds}"
    )

commit_end = datetime.utcfromtimestamp(distributor_info.commitEnd).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)
period_end = datetime.utcfromtimestamp(distributor_info.periodEnd).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

# configure burn
sender = USER_ACCOUNT.addr
user_balances = get_balances(indexer, sender)
user_holding = user_balances[govDispenser.gAlgoId]
amount_ask = input(f"Amount of gALGO to burn [{user_holding:_}]: ")
burn_amount = int(amount_ask) if amount_ask else user_holding
if burn_amount <= 0 or burn_amount > user_holding:
    raise ValueError(f"Burn amount {burn_amount} is out of range")

# show info
print(f"Dispenser appId: {govDispenser.appId}")
print(dispenser_info)
print(f"gALGO assetId: {govDispenser.gAlgoId}")
print(f"Distributor appId: {distributor.appId}")
print(f"Distributor commit end: {commit_end}")
print(f"Distributor period end: {period_end}")
print(f"User gALGO holding: {user_holding:_}")
print(f"Burn amount: {burn_amount:_}")

# prepare txns
params = client.algod.suggested_params()

burn_txns = prepareBurnTransactions(
    govDispenser, distributor, sender, burn_amount, params
)

# Prepare a transaction group
txn_group = assign_group_id(burn_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
