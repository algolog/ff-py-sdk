from algosdk.v2client.algod import AlgodClient
from ffsdk.config import Network
from ffsdk.lending.v2.datatypes import Account
from ffsdk.router.client import FolksRouterClient
from ffsdk.router.datatypes import SwapMode, SwapParams
from algosdk.encoding import msgpack_decode
from base64 import b64decode
import json


USER_ACCOUNT = Account(addr="", sk="")
client = FolksRouterClient(Network.MAINNET)

USDT = 312769
USDC = 31566704
amount = 100_000_000

# construct swap params
swap_params = SwapParams(
    fromAssetId=USDC,
    toAssetId=USDT,
    amount=amount,
    swapMode=SwapMode.FIXED_INPUT,
)

# fetch quote
quote = client.fetchSwapQuote(swap_params)
quote_payload = json.loads(b64decode(quote.txnPayload))
payload_data = quote_payload["data"]
paths = payload_data["paths"]
n_swaps = sum(len(p["swaps"]) for p in paths)

print(f"{quote.quoteAmount=:_}")
print(f"{quote.priceImpact=}")
print(f"{quote.microalgoTxnsFee=}")
print(f"N_paths: {len(paths)}")
print(f"N_swaps: {n_swaps}")

# prepare swap
fee_bps = 10  # 0.1%
base64_txns = client.prepareSwapTransactions(swap_params, USER_ACCOUNT.addr, fee_bps, quote)
unsigned_txns = [msgpack_decode(txn) for txn in base64_txns]
signed_txns = [txn.sign(USER_ACCOUNT.sk) for txn in unsigned_txns]
print(f"N_txns: {len(unsigned_txns)}")

# submit
algod = AlgodClient("", "https://mainnet-api.algonode.cloud")
res = algod.simulate_raw_transactions(signed_txns)  # simulate
txid = algod.send_transactions(signed_txns)
