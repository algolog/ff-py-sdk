from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from .config import Network
from .lend.client import LendingClient
from .algo_liquid_governance.v2.client import AlgoLiquidGovernanceClient
from .xalgo.client import XAlgoLiquidStakingClient


class FFClient:
    def __init__(self,
                 algod_client: AlgodClient,
                 indexer_client: IndexerClient,
                 network: Network):
        self.algod = algod_client
        self.indexer = indexer_client
        self.network = network

        # lending
        self.lending = LendingClient(self)

        # algo liquid governance
        self.algo_liquid_governance = AlgoLiquidGovernanceClient(self)

        # xALGO liquid staking
        self.xalgo = XAlgoLiquidStakingClient(self)


class FFTestnetClient(FFClient):
    def __init__(self, algod_client=None, indexer_client=None):
        if algod_client is None:
            algod_client = AlgodClient("", "https://testnet-api.algonode.cloud")
        if indexer_client is None:
            indexer_client = IndexerClient(
                    "",
                    "https://algoindexer.testnet.algoexplorerapi.io",
                    headers={"User-Agent": "algosdk"})
        super().__init__(
                algod_client,
                indexer_client,
                network=Network.TESTNET
        )


class FFMainnetClient(FFClient):
    def __init__(self, algod_client=None, indexer_client=None):
        if algod_client is None:
            algod_client = AlgodClient("", "https://mainnet-api.algonode.cloud")
        if indexer_client is None:
            indexer_client = IndexerClient("", "https://mainnet-idx.algonode.cloud",
                                           headers={"User-Agent": "algosdk"})
        super().__init__(
                algod_client,
                indexer_client,
                network=Network.MAINNET
        )
