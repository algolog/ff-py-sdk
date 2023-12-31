from ffsdk.config import Network
from .constants.mainnet_constants import (
        govDistributor8,
        govDistributor9,
        govDistributor10,
)


class AlgoLiquidGovernanceClient:
    def __init__(self, ff_client):
        """Constructor for the client used to interact with FolksFinance algo liquid governance protocol"""
        self.ff_client = ff_client
        self.algod = ff_client.algod
        self.indexer = ff_client.indexer
        self.network = ff_client.network

        if self.network == Network.MAINNET:
            self.distributor = govDistributor9
            self.prev_distributor = govDistributor8
            self.next_distributor = govDistributor10
        else:
            raise ValueError("Unsupported network.")
