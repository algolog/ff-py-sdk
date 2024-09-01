from ffsdk.config import Network
from .constants.mainnet_constants import consensusConfig
from .datatypes import ConsensusConfig


class XAlgoLiquidGovernanceClient:
    def __init__(self, ff_client):
        """Constructor for the client for interaction with FolksFinance xAlgo liquid governance protocol"""
        self.ff_client = ff_client
        self.algod = ff_client.algod
        self.indexer = ff_client.indexer
        self.network = ff_client.network

        if self.network == Network.MAINNET:
            self.consensus_config: ConsensusConfig = consensusConfig
        else:
            raise ValueError("Unsupported network.")
