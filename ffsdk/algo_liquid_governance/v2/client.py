from ffsdk.config import Network
from .constants import mainnet_constants


class AlgoLiquidGovernanceClient:
    def __init__(self, ff_client):
        """Constructor for the client used to interact with FolksFinance algo liquid governance protocol"""
        self.ff_client = ff_client
        self.algod = ff_client.algod
        self.indexer = ff_client.indexer
        self.network = ff_client.network

        if self.network == Network.MAINNET:
            self.distributor = mainnet_constants.LAST_DISTRIBUTOR
            self.next_distributor = mainnet_constants.NEXT_DISTRIBUTOR
        else:
            raise ValueError("Unsupported network.")
