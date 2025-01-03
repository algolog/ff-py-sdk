from ffsdk.config import Network
from .constants import MainnetConsensusConfig, TestnetConsensusConfig
from .datatypes import ConsensusConfig


class XAlgoLiquidStakingClient:
    def __init__(self, ff_client):
        """Constructor for the client for interaction with FolksFinance xALGO liquid staking protocol"""
        self.ff_client = ff_client
        self.algod = ff_client.algod
        self.indexer = ff_client.indexer
        self.network = ff_client.network

        if self.network == Network.MAINNET:
            self.consensus_config: ConsensusConfig = MainnetConsensusConfig
        elif self.network == Network.TESTNET:
            self.consensus_config: ConsensusConfig = TestnetConsensusConfig
        else:
            raise ValueError("Unsupported network.")
