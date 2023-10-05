from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import Account
from ffsdk.xalgo.governance import (
    getXAlgoInfo,
    prepareMintXAlgoTransactions,
    prepareBurnXAlgoTransactions,
)
from ffsdk.state_utils import get_balances
from datetime import datetime

USER_ACCOUNT = Account(addr="", sk="")

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "")

# init FolksFinance client and xalgo subclient
ff_client = FFMainnetClient(algod, indexer)
client = ff_client.xalgo

# get info
xalgo_info = getXAlgoInfo(client.indexer, client.distributor)

# mint
params = client.algod.suggested_params()
sender = USER_ACCOUNT.addr
mint_amount = 1_000_000
min_to_receive_after_mint = mint_amount * xalgo_info.xAlgoCirculatingBalance // xalgo_info.algoBalance
print(f"{mint_amount=:_}")
print(f"{min_to_receive_after_mint=:_}")

mint_txns = prepareMintXAlgoTransactions(
    xAlgo=client.distributor,
    senderAddr=sender,
    amount=mint_amount,
    minReceivedAmount=min_to_receive_after_mint,
    params=params,
    note=None
)
txn_group = assign_group_id(mint_txns)

# burn
burn_amount = 100_000
min_to_receive_after_burn = burn_amount * xalgo_info.algoBalance // xalgo_info.xAlgoCirculatingBalance
print(f"{burn_amount=:_}")
print(f"{min_to_receive_after_burn=:_}")
burn_txns = prepareBurnXAlgoTransactions(
    xAlgo=client.distributor,
    senderAddr=sender,
    amount=burn_amount,
    minReceivedAmount=min_to_receive_after_burn,
    params=params,
    note=None,
)
txn_group = assign_group_id(burn_txns)

# ffutils.ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk)
