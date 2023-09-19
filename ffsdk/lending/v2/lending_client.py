from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from ffsdk.config import Network
from .lending_config import LENDING_CONFIGS


class LendingClient:
    def __init__(self, ff_client):
        """Constructor for the client used to interact with FolksFinance lending protocol
        """
        self.ff_client = ff_client
        self.algod = ff_client.algod
        self.indexer = ff_client.indexer
        self.network = ff_client.network

        self.lending_config = LENDING_CONFIGS[self.network]
        self.pool_manager_app_id = self.lending_config.pool_manager_app_id
        self.deposits_app_id = self.lending_config.deposits_app_id
        self.deposit_staking_app_id = self.lending_config.deposit_staking_app_id
        self.pools = self.lending_config.pools
        self.loans = self.lending_config.loans
        self.lending_pools = self.lending_config.lending_pools
        self.reserve_address = self.lending_config.reserve_address
        self.oracle = self.lending_config.oracle
        self.opup = self.lending_config.opup
