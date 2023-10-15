from ffsdk.config import Network
import requests
from .datatypes import SwapMode, SwapQuote, SwapTransactions

BASE_URL = "https://api.folksrouter.io"
NETWORK_NAMES = {Network.MAINNET: "mainnet", Network.TESTNET: "testnet"}


class FolksRouterClient:
    def __init__(self, network: Network, api_key=None):
        """Constructor for the client used to interact with FolksFinance router"""
        url = BASE_URL
        if network == Network.TESTNET:
            url += "/testnet"
        url += "/v1"
        if api_key is not None:
            url += "/pro"

        # set
        self.network = NETWORK_NAMES[network]
        self.url = url
        self.api = requests.Session()
        self.api.headers.update({"x-api-key": api_key})

    def fetchSwapQuote(
        self,
        fromAssetId: int,
        toAssetId: int,
        amount: int,
        swapMode: SwapMode,
        maxGroupSize: int | None = None,
        feeBps: int | None = None,
        referrer: str | None = None,
    ) -> SwapQuote:
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
        userAddress: str,
        slippageBps: int,
        swapQuote: SwapQuote,
    ) -> SwapTransactions:
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

        return data["result"]
