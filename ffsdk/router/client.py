from ffsdk.config import Network
from algosdk import abi
from algosdk.encoding import msgpack_decode
from algosdk.logic import get_application_address
from algosdk.transaction import OnComplete
from algosdk.constants import PAYMENT_TXN, ASSETTRANSFER_TXN, APPCALL_TXN
from dataclasses import astuple
from .datatypes import SwapMode, SwapParams, SwapQuote, SwapTransactions
from .abi_contracts import routerABIContract
from .constants.mainnet_constants import MAINNET_FOLKS_ROUTER_APP_ID
from .constants.testnet_constants import TESTNET_FOLKS_ROUTER_APP_ID
from ..mathlib import mulScale, ONE_4_DP
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
        fromAssetId, toAssetId, amount, swapMode = astuple(params)

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
        if self.network == NETWORK_NAMES[Network.MAINNET]:
            folksRouterAppId = MAINNET_FOLKS_ROUTER_APP_ID
        else:
            folksRouterAppId = TESTNET_FOLKS_ROUTER_APP_ID
        folksRouterAddr = get_application_address(folksRouterAppId)

        def getHexSelector(method: str):
            return routerABIContract.get_method_by_name(method).get_selector().hex()

        sendAssetTxn = unsignedTxns[0]
        swapForwardTxns = unsignedTxns[1:-1]
        swapEndTxn = unsignedTxns[-1]
        if not swapForwardTxns:
            raise ValueError("Missing swap forward transactions")

        # send algo/asset
        if sendAssetTxn.rekey_to is not None:
            raise ValueError("Unexpected rekey")
        if sendAssetTxn.receiver != folksRouterAddr:
            raise ValueError("Incorrect receiver")

        if sendAssetTxn.type == PAYMENT_TXN:
            if fromAssetId != 0:
                raise ValueError("Sending algo instead of the asset")
            if sendAssetTxn.close_remainder_to is not None:
                raise ValueError("Unexpected close remainder to")
            sendAmount = sendAssetTxn.amt
        elif sendAssetTxn.type == ASSETTRANSFER_TXN:
            if fromAssetId != sendAssetTxn.index:
                raise ValueError("Sending incorrect asset")
            if sendAssetTxn.close_assets_to is not None:
                raise ValueError("Unexpected close assets to")
            sendAmount = sendAssetTxn.amount
        else:
            raise ValueError("Incorrect type of the first transaction")

        # swap forward txns
        SWAP_FORWARD_SELECTOR = getHexSelector("swap_forward")
        for txn in swapForwardTxns:
            if not (txn.type == APPCALL_TXN and txn.on_complete == OnComplete.NoOpOC):
                raise ValueError("Incorrect transaction type")
            if txn.index != folksRouterAppId:
                raise ValueError(f"Incorrect application index: {txn.index}")
            if txn.app_args[0].hex() != SWAP_FORWARD_SELECTOR:
                raise ValueError("Incorrect selector")

        # receive algo/asset
        if not (
            swapEndTxn.type == APPCALL_TXN
            and swapEndTxn.on_complete == OnComplete.NoOpOC
        ):
            raise ValueError("Incorrect closing transaction type")
        if swapEndTxn.index != folksRouterAppId:
            raise ValueError("Incorrect application index")
        swapEndSelector = swapEndTxn.app_args[0].hex()
        isFixedInput = swapEndSelector == getHexSelector("fi_end_swap")
        isFixedOutput = swapEndSelector == getHexSelector("fo_end_swap")
        if not (
            (isFixedInput and swapMode == SwapMode.FIXED_INPUT)
            or (isFixedOutput and swapMode == SwapMode.FIXED_OUTPUT)
        ):
            raise ValueError("Incorrect swap end selector")

        if abi.UintType(64).decode(swapEndTxn.app_args[1]) != toAssetId:
            raise ValueError("Receiving incorrect algo/asset")
        receiveAmount = abi.UintType(64).decode(swapEndTxn.app_args[2])

        # check amounts
        slippageAmount = mulScale(swapQuote.quoteAmount, int(slippageBps), ONE_4_DP)
        if isFixedInput:
            if amount != sendAmount:
                raise ValueError("Sending incorrect fixed input amount")
            if (swapQuote.quoteAmount - slippageAmount) != receiveAmount:
                raise ValueError("Receiving incorrect fixed input amount")
        if isFixedOutput:
            if (swapQuote.quoteAmount + slippageAmount) != sendAmount:
                raise ValueError("Sending incorrect fixed output amount")
            if amount != receiveAmount:
                raise ValueError("Receiving incorrect fixed output amount")

        # return
        return data["result"]
