from ffsdk.config import Network
from algosdk.encoding import msgpack_decode
from dataclasses import astuple
from .datatypes import SwapParams, SwapQuote, SwapTransactions
from .checks import checkSwapTransactions
import requests

BASE_URL = "https://api.folksrouter.io"
NETWORK_NAMES = {Network.MAINNET: "mainnet", Network.TESTNET: "testnet"}


class FolksRouterClient:
    def __init__(self, network: Network, api_key=None):
        """Constructor for the client used to interact with FolksFinance router"""
        url = BASE_URL
        if network == Network.TESTNET:
            url += "/testnet"
        url += "/v2"
        if api_key is not None:
            url += "/pro"

        # set
        self.network_type = network
        self.network = NETWORK_NAMES[network]
        self.url = url
        self.api = requests.Session()
        self.api.headers.update({"x-api-key": api_key})

    def fetchUserDiscount(self, userAddress: str) -> int:
        r = self.api.get(
            self.url + "/fetch/discount",
            params={
                "network": self.network,
                "userAddress": userAddress,
            },
        )
        r.raise_for_status()
        data = r.json()["result"]
        return data

    def fetchSwapQuote(
        self,
        params: SwapParams,
        maxGroupSize: int | None = None,
        feeBps: int | None = None,
        userFeeDiscount: int | None = None,
        referrer: str | None = None,
    ) -> SwapQuote:
        fromAssetId, toAssetId, amount, swapMode = astuple(params)

        r = self.api.get(
            self.url + "/fetch/quote",
            params={
                "network": self.network,
                "fromAsset": fromAssetId,
                "toAsset": toAssetId,
                "amount": amount,
                "type": swapMode.value,
                "maxGroupSize": maxGroupSize,
                "feeBps": feeBps,
                "userFeeDiscount": userFeeDiscount,
                "referrer": referrer,
            },
        )
        r.raise_for_status()

        data = r.json()["result"]

        return SwapQuote(
            int(data["quoteAmount"]),
            data["priceImpact"],
            data["microalgoTxnsFee"],
            data["txnPayload"],
        )

    def prepareSwapTransactions(
        self,
        params: SwapParams,
        userAddress: str,
        slippageBps: int,
        swapQuote: SwapQuote,
    ) -> SwapTransactions:
        # fetch transactions
        r = self.api.get(
            self.url + "/prepare/swap",
            params={
                "userAddress": userAddress,
                "slippageBps": slippageBps,
                "txnPayload": swapQuote.txnPayload,
            },
        )
        r.raise_for_status()
        data = r.json()

        # check transactions
        unsignedTxns = [msgpack_decode(txn) for txn in data["result"]]
        checkSwapTransactions(
            self.network_type, unsignedTxns, params, userAddress, slippageBps, swapQuote
        )

        # return
        return data["result"]
