from ffsdk.config import Network
from .datatypes import LendingConfig, Pool, PactLendingPool, Oracle, OpUp
from .constants.mainnet_constants import (
    MAINNET_POOL_MANAGER_APP_ID,
    MAINNET_DEPOSITS_APP_ID,
    MAINNET_DEPOSIT_STAKING_APP_ID,
    MainnetPools,
    MainnetLoans,
    MainnetLendingPools,
    MAINNET_RESERVE_ADDRESS,
    MainnetOracle,
    MainnetOpUp,
)
from .constants.testnet_constants import (
    TESTNET_POOL_MANAGER_APP_ID,
    TESTNET_DEPOSITS_APP_ID,
    TestnetPools,
    TestnetLoans,
    TESTNET_RESERVE_ADDRESS,
    TestnetOracle,
    TestnetOpUp,
)


LENDING_CONFIGS = {
    Network.MAINNET: LendingConfig(
        MAINNET_POOL_MANAGER_APP_ID,
        MAINNET_DEPOSITS_APP_ID,
        MAINNET_DEPOSIT_STAKING_APP_ID,
        {k: Pool(**v) for k, v in MainnetPools.items()},
        MainnetLoans,
        {k: PactLendingPool(**v) for k, v in MainnetLendingPools.items()},
        MAINNET_RESERVE_ADDRESS,
        Oracle(**MainnetOracle),
        OpUp(**MainnetOpUp)
    ),
    Network.TESTNET: LendingConfig(
        TESTNET_POOL_MANAGER_APP_ID,
        TESTNET_DEPOSITS_APP_ID,
        None,
        {k: Pool(**v) for k, v in TestnetPools.items()},
        TestnetLoans,
        None,
        TESTNET_RESERVE_ADDRESS,
        Oracle(**TestnetOracle),
        OpUp(**TestnetOpUp)
    ),
}
