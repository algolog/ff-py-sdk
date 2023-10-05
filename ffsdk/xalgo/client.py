from ffsdk.config import Network
from .constants.mainnet_constants import xGovDistributor
from .datatypes import XAlgo


class XAlgoLiquidGovernanceClient:
    def __init__(self, ff_client):
        """Constructor for the client used to interact with FolksFinance xAlgo liquid governance protocol"""
        self.ff_client = ff_client
        self.algod = ff_client.algod
        self.indexer = ff_client.indexer
        self.network = ff_client.network

        if self.network == Network.MAINNET:
            self.distributor: XAlgo = xGovDistributor
            self.xAlgo: XAlgo = xGovDistributor  # short alias for convinience
        else:
            raise ValueError("Unsupported network.")
