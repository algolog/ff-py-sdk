from dataclasses import dataclass
from enum import Enum
from typing import Optional


# LENDING POOL TYPES


class LPTokenProvider(Enum):
    TINYMAN = 0
    PACT = 1


@dataclass(kw_only=True)
class BaseLPToken:
    provider: LPTokenProvider
    lpAssetId: int
    asset0Id: int
    asset1Id: int


@dataclass(kw_only=True)
class TinymanLPToken(BaseLPToken):
    provider: LPTokenProvider = LPTokenProvider.TINYMAN
    lpPoolAddress: str


@dataclass(kw_only=True)
class PactLPToken(BaseLPToken):
    provider: LPTokenProvider = LPTokenProvider.PACT
    lpPoolAppId: int


LPToken = TinymanLPToken | PactLPToken


@dataclass(kw_only=True)
class BaseLendingPool(BaseLPToken):
    pool0AppId: int
    pool1AppId: int
    feeScale: int


@dataclass(kw_only=True)
class PactLendingPool(BaseLendingPool):
    provider: LPTokenProvider = LPTokenProvider.PACT
    lpPoolAppId: int


@dataclass(kw_only=True)
class TinymanLendingPool(BaseLendingPool):
    provider: LPTokenProvider = LPTokenProvider.TINYMAN
    lpPoolAppAddress: int


LendingPool = PactLendingPool | TinymanLendingPool


@dataclass
class LendingPoolInterest:
    asset0DepositInterestRate: int  # 16 d.p.
    asset0DepositInterestYield: int  # approximation 16 d.p.
    asset1DepositInterestRate: int  # 16 d.p.
    asset1DepositInterestYield: int  # approximation 16 d.p.
    additionalInterestRate: int | None  # 16 d.p.
    additionalInterestYield: int | None  # approximation 16 d.p.


@dataclass
class BaseLendingPoolInfo:
    fAsset0Supply: int
    fAsset1Supply: int
    liquidityTokenCirculatingSupply: int
    fee: int
    swapFeeInterestRate: int  # 16 d.p.
    swapFeeInterestYield: int  # 16 d.p.
    asset0DepositInterestRate: int  # 16 d.p.
    asset0DepositInterestYield: int  # approximation 16 d.p.
    asset1DepositInterestRate: int  # 16 d.p.
    asset1DepositInterestYield: int  # approximation 16 d.p.
    additionalInterestRate: int | None  # 16 d.p.
    additionalInterestYield: int | None  # approximation 16 d.p.
    tvlUsd: float


@dataclass
class PactLendingPoolInfo(BaseLendingPoolInfo):
    pass


@dataclass
class TinymanLendingPoolInfo(BaseLendingPoolInfo):
    farmInterestYield: int  # 16 d.p.


# DEPOSIT TYPES


@dataclass
class PoolMetadataFromManager:
    oldVariableBorrowInterestIndex: int  # 14 d.p.
    oldDepositInterestIndex: int  # 14 d.p.
    oldTimestamp: int


@dataclass
class PoolStateFromManager:
    variableBorrowInterestRate: int  # 16 d.p.
    variableBorrowInterestYield: int  # approximation 16 d.p.
    variableBorrowInterestIndex: int  # 14 d.p.
    depositInterestRate: int  # 16 d.p.
    depositInterestYield: int  # approximation 16 d.p.
    depositInterestIndex: int  # 14 d.p.
    metadata: PoolMetadataFromManager


@dataclass
class PoolManagerInfo:
    pools: dict[int, PoolStateFromManager]  # poolAppId -> ...


@dataclass
class Pool:
    appId: int
    assetId: int
    fAssetId: int
    frAssetId: int
    assetDecimals: int
    poolManagerIndex: int
    loans: dict[int, int]  # loanAppId -> loanIndex


@dataclass
class PoolInfo_VariableBorrow:
    vr0: int  # 16 d.p.
    vr1: int  # 16 d.p.
    vr2: int  # 16 d.p.
    totalVariableBorrowAmount: int
    variableBorrowInterestRate: int  # 16 d.p.
    variableBorrowInterestYield: int  # approximation 16 d.p.
    variableBorrowInterestIndex: int  # 14 d.p.


@dataclass
class PoolInfo_StableBorrow:
    sr0: int  # 16 d.p.
    sr1: int  # 16 d.p.
    sr2: int  # 16 d.p.
    sr3: int  # 16 d.p.
    optimalStableToTotalDebtRatio: int  # 16 d.p.
    rebalanceUpUtilisationRatio: int  # 16 d.p.
    rebalanceUpDepositInterestRate: int  # 16 d.p.
    rebalanceDownDelta: int  # 16 d.p.
    totalStableBorrowAmount: int
    stableBorrowInterestRate: int  # 16 d.p.
    stableBorrowInterestYield: int  # approximation 16 d.p.
    overallStableBorrowInterestAmount: int  # 16 d.p.


@dataclass
class PoolInfo_Interest:
    retentionRate: int  # 16 d.p.
    flashLoanFee: int  # 16 d.p.
    optimalUtilisationRatio: int  # 16 d.p.
    totalDeposits: int
    depositInterestRate: int  # 16 d.p.
    depositInterestYield: int  # approximation 16 d.p.
    depositInterestIndex: int  # 14 d.p.
    latestUpdate: int


@dataclass
class PoolInfo_Caps:
    borrowCap: int  # $ value
    stableBorrowPercentageCap: int  # 16 d.p.


@dataclass
class PoolInfo_Config:
    depreciated: bool
    rewardsPaused: bool
    stableBorrowSupported: bool
    flashLoanSupported: bool


@dataclass
class PoolInfo:
    variableBorrow: PoolInfo_VariableBorrow
    stableBorrow: PoolInfo_StableBorrow
    interest: PoolInfo_Interest
    caps: PoolInfo_Caps
    config: PoolInfo_Config


@dataclass
class UserDepositHolding:
    fAssetId: int
    fAssetBalance: int


@dataclass
class UserDepositInfo:
    escrowAddress: str
    holdings: list[UserDepositHolding]


@dataclass
class UserDepositFullHolding:
    fAssetId: int
    fAssetBalance: int
    poolAppId: int
    assetId: int
    assetPrice: int  # 14 d.p.
    assetBalance: int
    balanceValue: int  # in $, 4 d.p.
    interestRate: int  # 16 d.p.
    interestYield: int  # approximation 16 d.p.


@dataclass
class UserDepositFullInfo:
    escrowAddress: str
    holdings: list[UserDepositFullHolding]


# DEPOSIT STAKING TYPES


@dataclass
class DSInfoReward:
    rewardAssetId: int
    endTimestamp: int
    rewardRate: int  # 10 d.p.
    rewardPerToken: int  # 10 d.p.


@dataclass
class DSInfoProgram:
    poolAppId: int
    totalStaked: int
    minTotalStaked: int
    stakeIndex: int
    numRewards: int
    rewards: list[DSInfoReward]


@dataclass
class DepositStakingInfo:
    stakingPrograms: list[DSInfoProgram]


@dataclass
class DSPInfoReward:
    rewardAssetId: int
    endTimestamp: int
    rewardRate: int  # 10 d.p.
    rewardPerToken: int  # 10 d.p.
    rewardAssetPrice: int  # 14 d.p.
    rewardInterestRate: int  # 0 if past reward end timestamp, 16 d.p.


@dataclass
class DepositStakingProgramInfo:
    poolAppId: int
    stakeIndex: int
    fAssetId: int
    fAssetTotalStakedAmount: int
    assetId: int
    assetPrice: int  # 14 d.p.
    assetTotalStakedAmount: int
    totalStakedAmountValue: int  # in $, 4 d.p.
    depositInterestRate: int  # 16 d.p.
    depositInterestYield: int  # approximation 16 d.p.
    rewards: list[DSPInfoReward]


@dataclass
class UserDepositStakingLocalState:
    userAddress: str
    escrowAddress: str
    optedIntoAssets: set[int]
    stakedAmounts: list[int]
    rewardPerTokens: list[int]  # 10 d.p.
    unclaimedRewards: list[int]


@dataclass
class UDSPInfoReward:
    rewardAssetId: int
    endTimestamp: int
    rewardAssetPrice: int  # 14 d.p.
    rewardInterestRate: int  # 0 if past reward end timestamp, 16 d.p.
    unclaimedReward: int
    unclaimedRewardValue: int  # in $, 4 d.p.


@dataclass
class UserDepositStakingProgramInfo:
    poolAppId: int
    fAssetId: int
    fAssetStakedAmount: int
    assetId: int
    assetPrice: int  # 14 d.p.
    assetStakedAmount: int
    stakedAmountValue: int  # in $, 4 d.p.
    depositInterestRate: int  # 16 d.p.
    depositInterestYield: int  # approximation 16 d.p.
    rewards: list[UDSPInfoReward]


@dataclass
class UserDepositStakingInfo:
    userAddress: str
    escrowAddress: str
    optedIntoAssets: set[int]
    stakingPrograms: list[UserDepositStakingProgramInfo]


# LOAN TYPES


@dataclass
class PoolLoanInfo:
    poolAppId: int
    assetId: int
    collateralCap: int  # $ value
    collateralUsed: int
    collateralFactor: int  # 4 d.p.
    borrowFactor: int  # 4 d.p.
    liquidationMax: int  # 4 d.p.
    liquidationBonus: int  # 4 d.p.
    liquidationFee: int  # 4 d.p.


class LoanType(Enum):
    GENERAL = 0
    STABLECOIN_EFFICIENCY = 1
    ALGO_EFFICIENCY = 2
    ULTRASWAP_UP = 3
    ULTRASWAP_DOWN = 4
    ALGORAND_ECOSYSTEM = 5


@dataclass
class LoanInfo:
    canSwapCollateral: bool
    pools: dict[int, PoolLoanInfo]  # poolAppId -> PoolLoanInfo


@dataclass
class LLSCollateral:
    poolAppId: int
    fAssetBalance: int


@dataclass
class LLSBorrow:
    poolAppId: int
    borrowedAmount: int
    borrowBalance: int
    latestBorrowInterestIndex: int  # 14 d.p.
    stableBorrowInterestRate: int  # 16 d.p.
    latestStableChange: int


@dataclass
class LoanLocalState:
    userAddress: str
    escrowAddress: str
    collaterals: list[LLSCollateral]
    borrows: list[LLSBorrow]


@dataclass
class UserLoanInfoCollateral:
    poolAppId: int
    assetId: int
    assetPrice: int  # 14 d.p.
    collateralFactor: int  # 4 d.p.
    depositInterestIndex: int  # 14 d.p.
    fAssetBalance: int
    assetBalance: int
    balanceValue: int  # in $, 4 d.p.
    effectiveBalanceValue: int  # in $, 4 d.p.
    interestRate: int  # 16 d.p.
    interestYield: int  # approximation 16 d.p.


@dataclass
class UserLoanInfoBorrow:
    poolAppId: int
    assetId: int
    assetPrice: int  # 14 d.p.
    isStable: bool
    borrowFactor: int  # 4 d.p.
    borrowedAmount: int
    borrowedAmountValue: int  # in $, 4 d.p.
    borrowBalance: int
    borrowBalanceValue: int  # in $, 4 d.p.
    effectiveBorrowBalanceValue: int  # in $, 4 d.p.
    accruedInterest: int
    accruedInterestValue: int  # in $, 4 d.p.
    interestRate: int  # 16 d.p.
    interestYield: int  # approximation 16 d.p.


@dataclass
class UserLoanInfo:
    userAddress: str
    escrowAddress: str
    collaterals: list[UserLoanInfoCollateral]
    borrows: list[UserLoanInfoBorrow]
    netRate: int  # 16 d.p. - negative indicates losing more on borrows than gaining on collaterals
    netYield: int  # 16 d.p. - negative indicates losing more on borrows than gaining on collaterals
    totalCollateralBalanceValue: int  # in $, 4 d.p.
    totalBorrowedAmountValue: int  # in $, 4 d.p.
    totalBorrowBalanceValue: int  # in $, 4 d.p.
    totalEffectiveCollateralBalanceValue: int  # in $, 4 d.p. - used to determine if liquidatable
    totalEffectiveBorrowBalanceValue: int  # in $, 4 d.p. - used to determine if liquidatable
    loanToValueRatio: int  # 4 d.p.
    borrowUtilisationRatio: int  # 4 d.p.
    liquidationMargin: int  # 4 d.p.


@dataclass
class AssetAdditionalInterest:
    rateBps: int  # 4 d.p.
    yieldBps: int  # 4 d.p.


AssetsAdditionalInterest = dict[int, AssetAdditionalInterest]  # assetId -> interest


# ORACLE TYPES


@dataclass
class LPTokenOracle:
    appId: int
    tinymanValidatorAppId: int


@dataclass
class Oracle:
    oracle0AppId: int
    oracleAdapterAppId: int
    decimals: int
    oracle1AppId: Optional[int] = None
    lpTokenOracle: Optional[LPTokenOracle] = None


@dataclass
class OraclePrice:
    price: int  # price in USD for amount 1 of asset in lowest denomination
    timestamp: int


OraclePrices = dict[int, OraclePrice]  # assetId -> OraclePrice


# EXTRA TYPES


@dataclass
class Account:
    addr: str
    sk: str


@dataclass
class OpUp:
    callerAppId: int
    baseAppId: int


# LENDING_CONFIG TYPES


@dataclass
class LendingConfig:
    pool_manager_app_id: int
    deposits_app_id: int
    deposit_staking_app_id: int
    pools: dict[str, Pool]  # market_name -> Pool
    loans: dict[LoanType, int]
    pact_lending_pools: dict[str, PactLendingPool]
    tinyman_lending_pools: dict[str, TinymanLendingPool]
    reserve_address: str
    oracle: Oracle
    opup: OpUp
