from ffsdk.config import Network
from .datatypes import (
    LendingConfig,
    Pool,
    LPTokenProvider,
    PactLendingPool,
    TinymanLendingPool,
    Oracle,
    OpUp,
)
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
        {
            k: PactLendingPool(**lpdata)
            for k, lpdata in MainnetLendingPools.items()
            if lpdata["provider"] == LPTokenProvider.PACT
        },
        {
            k: TinymanLendingPool(**lpdata)
            for k, lpdata in MainnetLendingPools.items()
            if lpdata["provider"] == LPTokenProvider.TINYMAN
        },
        MAINNET_RESERVE_ADDRESS,
        Oracle(**MainnetOracle),
        OpUp(**MainnetOpUp),
    ),
    Network.TESTNET: LendingConfig(
        TESTNET_POOL_MANAGER_APP_ID,
        TESTNET_DEPOSITS_APP_ID,
        None,
        {k: Pool(**v) for k, v in TestnetPools.items()},
        TestnetLoans,
        None,  # pact lending pools
        None,  # tinyman lending pools
        TESTNET_RESERVE_ADDRESS,
        Oracle(**TestnetOracle),
        OpUp(**TestnetOpUp),
    ),
}
