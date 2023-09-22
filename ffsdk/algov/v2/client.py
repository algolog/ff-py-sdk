from ffsdk.config import Network
from .constants.mainnet_constants import govDistributor8, govDistributor7


class AlgoLiquidGovernanceClient:
    def __init__(self, ff_client):
        """Constructor for the client used to interact with FolksFinance algo liquid governance protocol"""
        self.ff_client = ff_client
        self.algod = ff_client.algod
        self.indexer = ff_client.indexer
        self.network = ff_client.network

        if self.network == Network.MAINNET:
            self.distributor = govDistributor8
            self.prev_distributor = govDistributor7
        else:
            raise ValueError("Unsupported network.")
