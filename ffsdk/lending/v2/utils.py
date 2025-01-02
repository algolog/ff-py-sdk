from algosdk.v2client.indexer import IndexerClient
from algosdk.logic import get_application_address
from algosdk.encoding import encode_address
from time import time
from base64 import b64decode
from ...state_utils import (
    parse_uint64s,
    format_state,
    get_accounts_opted_into_app
)
from ...mathlib import (
    ONE_10_DP,
    ONE_16_DP,
    ONE_4_DP,
    SECONDS_IN_YEAR,
    compoundEverySecond,
    mulScale,
)
from .formulae import (
    calcBorrowAssetLoanValue,
    calcBorrowBalance,
    calcBorrowInterestIndex,
    calcBorrowUtilisationRatio,
    calcCollateralAssetLoanValue,
    calcLiquidationMargin,
    calcLTVRatio,
    calcWithdrawReturn,
)
from .datatypes import (
    DepositStakingInfo,
    DepositStakingProgramInfo,
    DSPInfoReward,
    LoanInfo,
    LoanLocalState,
    LLSCollateral,
    LLSBorrow,
    OraclePrices,
    Pool,
    PoolManagerInfo,
    UserDepositStakingInfo,
    UserDepositStakingLocalState,
    UserDepositStakingProgramInfo,
    UDSPInfoReward,
    UserLoanInfo,
    UserLoanInfoBorrow,
    UserLoanInfoCollateral,
)


def getEscrows(
    indexer: IndexerClient,
    userAddr: str,
    appId: int,
    addNotePrefix: str,
    removeNotePrefix: str,
) -> set[str]:
    """
    Returns set of user escrow addresses.
    """
    escrows: set[str] = set()
    appAddress = get_application_address(appId)

    added = indexer.search_transactions(
        address=userAddr,
        address_role="sender",
        txn_type="pay",
        note_prefix=addNotePrefix.encode(),
    )
    removed = indexer.search_transactions(
        address=userAddr,
        address_role="receiver",
        txn_type="pay",
        note_prefix=removeNotePrefix.encode(),
    )

    for txn in added.get("transactions"):
        receiver = txn["payment-transaction"]["receiver"]
        if receiver == appAddress:
            note = b64decode(txn["note"])
            address = encode_address(note[len(addNotePrefix) :])
            escrows.add(address)

    for txn in removed.get("transactions"):
        sender = txn["sender"]
        escrows.remove(sender)

    return escrows


def getAppEscrowsWithState(
    indexer: IndexerClient,
    appId: int,
) -> list[tuple[str, dict]]:
    """
    Returns all escrow accounts opted into a given app with their local state.
    """
    all_escrows: list[tuple[str, dict]] = []

    for account in get_accounts_opted_into_app(
        indexer, appId, exclude="assets,created-assets,created-apps"
    ):
        escrow_addr = account["address"]
        user_local_state = account.get("apps-local-state", [])
        for app_local_state in user_local_state:
            if app_local_state["id"] == appId:
                state = format_state(app_local_state.get("key-value", []))
                all_escrows.append((escrow_addr, state))

    return all_escrows


def depositStakingLocalState(
    state: dict,
    depositStakingAppId: int,
    escrowAddr: str,
) -> UserDepositStakingLocalState:
    """
    Derives deposit staking local state from escrow account.

    @param state - escrow account local state
    @param depositStakingAppId - deposit staking application to query about
    @param escrowAddr - escrow address
    @returns UserDepositStakingLocalState user deposit staking local state
    """
    # standard
    userAddress = encode_address(b64decode(state.get("ua")))

    stakedAmounts: list[int] = []
    for i in range(2):
        stakeBase64Value = state.get(f"S{i:c}")
        stakeValue = parse_uint64s(stakeBase64Value)
        stakedAmounts.extend(stakeValue)

    rewardPerTokens: list[int] = []
    for i in range(6):
        rewardBase64Value = state.get(f"R{i:c}")
        rewardValue = parse_uint64s(rewardBase64Value)
        rewardPerTokens.extend(rewardValue)

    unclaimedRewards: list[int] = []
    for i in range(6):
        unclaimedBase64Value = state.get(f"U{i:c}")
        rewardValue = parse_uint64s(rewardBase64Value)
        unclaimedValue = parse_uint64s(unclaimedBase64Value)
        unclaimedRewards.extend(unclaimedValue)

    return UserDepositStakingLocalState(
        userAddress,
        escrowAddr,
        optedIntoAssets=set(),
        stakedAmounts=stakedAmounts,
        rewardPerTokens=rewardPerTokens,
        unclaimedRewards=unclaimedRewards,
    )


def depositStakingProgramsInfo(
    depositStakingInfo: DepositStakingInfo,
    poolManagerInfo: PoolManagerInfo,
    pools: dict[str, Pool],
    oraclePrices: OraclePrices,
) -> list[DepositStakingProgramInfo]:
    """
    Derives deposit staking programs info from deposit staking info.
    Use for advanced use cases where optimising number of network request.

    @param depositStakingInfo - deposit staking info which is returned by retrieveDepositStakingInfo function
    @param poolManagerInfo - pool manager info which is returned by retrievePoolManagerInfo function
    @param pools - pools in pool manager (either MainnetPools or TestnetPools)
    @param oraclePrices - oracle prices which is returned by getOraclePrices function
    @returns Promise<DepositStakingProgramInfo[]> deposit staking programs info
    """

    stakingPrograms: list[DepositStakingProgramInfo] = []
    poolManagerPools = poolManagerInfo.pools
    prices = oraclePrices

    for sp in filter(lambda x: x.poolAppId != 0, depositStakingInfo.stakingPrograms):
        poolAppId = sp.poolAppId
        totalStaked = sp.totalStaked
        minTotalStaked = sp.minTotalStaked
        stakeIndex = sp.stakeIndex
        rewards = sp.rewards

        pool = next((x for x in pools.values() if x.appId == poolAppId), None)
        poolInfo = poolManagerPools.get(poolAppId)
        if pool is None or poolInfo is None:
            raise KeyError(f"Could not find pool {poolAppId}")
        assetId, fAssetId = pool.assetId, pool.fAssetId
        depositInterestIndex = poolInfo.depositInterestIndex
        depositInterestRate = poolInfo.depositInterestRate
        depositInterestYield = poolInfo.depositInterestYield
        oraclePrice = prices[assetId]
        assetPrice = oraclePrice.price

        fAssetTotalStakedAmount = max(totalStaked, minTotalStaked)
        assetTotalStakedAmount = calcWithdrawReturn(
            fAssetTotalStakedAmount, depositInterestIndex
        )
        totalStakedAmountValue = mulScale(
            assetTotalStakedAmount, assetPrice, ONE_10_DP
        )  # 4 d.p.

        userRewards: list[DSPInfoReward] = []
        for r in rewards:
            rewardAssetId = r.rewardAssetId
            endTimestamp = r.endTimestamp
            rewardRate = r.rewardRate
            rewardPerToken = r.rewardPerToken

            rewardAssetPrice = prices[rewardAssetId].price
            stakedAmountValue = assetTotalStakedAmount * assetPrice
            if time() < endTimestamp and stakedAmountValue != 0:
                rewardInterestRate = int(
                    (rewardRate * int(1e6) * rewardAssetPrice * SECONDS_IN_YEAR)
                    / stakedAmountValue
                )
            else:
                rewardInterestRate = 0

            userRewards.append(
                DSPInfoReward(
                    rewardAssetId=rewardAssetId,
                    endTimestamp=endTimestamp,
                    rewardRate=rewardRate,
                    rewardPerToken=rewardPerToken,
                    rewardAssetPrice=rewardAssetPrice,
                    rewardInterestRate=rewardInterestRate,
                )
            )

        stakingPrograms.append(
            DepositStakingProgramInfo(
                poolAppId,
                stakeIndex,
                fAssetId,
                fAssetTotalStakedAmount,
                assetId,
                assetPrice,
                assetTotalStakedAmount,
                totalStakedAmountValue,
                depositInterestRate,
                depositInterestYield,
                rewards=userRewards,
            )
        )

    return stakingPrograms


def userDepositStakingInfo(
    localState: UserDepositStakingLocalState,
    poolManagerInfo: PoolManagerInfo,
    depositStakingProgramsInfo: list[DepositStakingProgramInfo],
) -> UserDepositStakingInfo:
    """
    Derives user loan info from escrow account.
    Use for advanced use cases where optimising number of network request.

    @param localState - local state of escrow account
    @param poolManagerInfo - pool manager info which is returned by retrievePoolManagerInfo function*
    @param depositStakingProgramsInfo - deposit staking programs info which is returned by depositStakingProgramsInfo function
    @returns Promise<UserDepositStakingInfo> user loans info
    """

    stakingPrograms: list[UserDepositStakingProgramInfo] = []
    poolManagerPools = poolManagerInfo.pools

    for stakeIndex, stakingProgram in enumerate(depositStakingProgramsInfo):
        poolAppId = stakingProgram.poolAppId
        fAssetId = stakingProgram.fAssetId
        assetId = stakingProgram.assetId
        assetPrice = stakingProgram.assetPrice
        depositInterestRate = stakingProgram.depositInterestRate
        depositInterestYield = stakingProgram.depositInterestYield
        rewards = stakingProgram.rewards

        poolInfo = poolManagerPools[poolAppId]
        depositInterestIndex = poolInfo.depositInterestIndex

        fAssetStakedAmount = localState.stakedAmounts[stakeIndex]
        assetStakedAmount = calcWithdrawReturn(fAssetStakedAmount, depositInterestIndex)
        stakedAmountValue = mulScale(assetStakedAmount, assetPrice, ONE_10_DP)  # 4 d.p.

        userRewards: list[UDSPInfoReward] = []

        for localRewardIndex, r in enumerate(rewards):
            rewardAssetId = r.rewardAssetId
            endTimestamp = r.endTimestamp
            rewardAssetPrice = r.rewardAssetPrice
            rewardInterestRate = r.rewardInterestRate
            rewardPerToken = r.rewardPerToken

            rewardIndex = stakeIndex * 3 + localRewardIndex
            oldRewardPerToken = localState.rewardPerTokens[rewardIndex]
            oldUnclaimedReward = localState.unclaimedRewards[rewardIndex]

            unclaimedReward = oldUnclaimedReward + mulScale(
                fAssetStakedAmount, rewardPerToken - oldRewardPerToken, ONE_10_DP
            )
            unclaimedRewardValue = mulScale(
                unclaimedReward, rewardAssetPrice, ONE_10_DP
            )  # 4 d.p.

            userRewards.append(
                UDSPInfoReward(
                    rewardAssetId=rewardAssetId,
                    endTimestamp=endTimestamp,
                    rewardAssetPrice=rewardAssetPrice,
                    rewardInterestRate=rewardInterestRate,
                    unclaimedReward=unclaimedReward,
                    unclaimedRewardValue=unclaimedRewardValue,
                )
            )

        stakingPrograms.append(
            UserDepositStakingProgramInfo(
                poolAppId=poolAppId,
                fAssetId=fAssetId,
                fAssetStakedAmount=fAssetStakedAmount,
                assetId=assetId,
                assetPrice=assetPrice,
                assetStakedAmount=assetStakedAmount,
                stakedAmountValue=stakedAmountValue,
                depositInterestRate=depositInterestRate,
                depositInterestYield=depositInterestYield,
                rewards=userRewards,
            )
        )

    return UserDepositStakingInfo(
        userAddress=localState.userAddress,
        escrowAddress=localState.escrowAddress,
        optedIntoAssets=localState.optedIntoAssets,
        stakingPrograms=stakingPrograms,
    )


def loanLocalState(state: dict, loanAppId: int, escrowAddr: str) -> LoanLocalState:
    """
    Derives loan local state from escrow account.

    @param state - escrow account local state
    @param loanAppId - loan application to query about
    @param escrowAddr - escrow address
    @returns LoanLocalState loan local state
    """
    # standard
    userAddress = encode_address(b64decode(state.get("u")))
    colPls = parse_uint64s(state.get("c"))
    borPls = parse_uint64s(state.get("b"))
    colBals = parse_uint64s(state.get("cb"))
    borAms = parse_uint64s(state.get("ba"))
    borBals = parse_uint64s(state.get("bb"))
    lbii = parse_uint64s(state.get("l"))
    sbir = parse_uint64s(state.get("r"))
    lsc = parse_uint64s(state.get("t"))

    # custom
    collaterals: list[LLSCollateral] = []
    borrows: list[LLSBorrow] = []
    for i in range(15):
        # add collateral
        collaterals.append(
            LLSCollateral(
                poolAppId=int(colPls[i]),
                fAssetBalance=colBals[i],
            )
        )

        # add borrow
        borrows.append(
            LLSBorrow(
                poolAppId=int(borPls[i]),
                borrowedAmount=borAms[i],
                borrowBalance=borBals[i],
                latestBorrowInterestIndex=lbii[i],
                stableBorrowInterestRate=sbir[i],
                latestStableChange=lsc[i],
            )
        )

    return LoanLocalState(
        userAddress=userAddress,
        escrowAddress=escrowAddr,
        collaterals=collaterals,
        borrows=borrows,
    )


def userLoanInfo(
    localState: LoanLocalState,
    poolManagerInfo: PoolManagerInfo,
    loanInfo: LoanInfo,
    oraclePrices: OraclePrices,
) -> UserLoanInfo:
    """
    Derives user loan info from escrow account.
    Use for advanced use cases where optimising number of network request.

    @param localState - local state of escrow account
    @param poolManagerInfo - pool manager info which is returned by retrievePoolManagerInfo function
    @param loanInfo - loan info which is returned by retrieveLoanInfo function
    @param oraclePrices - oracle prices which is returned by getOraclePrices function
    @returns Promise<UserLoansInfo> user loans info
    """
    poolManagerPools = poolManagerInfo.pools
    loanPools = loanInfo.pools
    prices = oraclePrices

    netRate: int = 0
    netYield: int = 0

    # collaterals
    collaterals: list[UserLoanInfoCollateral] = []
    totalCollateralBalanceValue: int = 0
    totalEffectiveCollateralBalanceValue: int = 0

    for col in localState.collaterals:
        poolAppId = col.poolAppId
        fAssetBalance = col.fAssetBalance

        isColPresent = poolAppId > 0
        if not isColPresent:
            continue

        poolInfo = poolManagerPools.get(poolAppId)
        poolLoanInfo = loanPools.get(poolAppId)
        if poolInfo is None or poolLoanInfo is None:
            raise KeyError(f"Could not find collateral pool {poolAppId}")

        depositInterestIndex = poolInfo.depositInterestIndex
        depositInterestRate = poolInfo.depositInterestRate
        depositInterestYield = poolInfo.depositInterestYield
        assetId = poolLoanInfo.assetId
        collateralFactor = poolLoanInfo.collateralFactor
        oraclePrice = prices.get(assetId)
        if oraclePrice is None:
            raise KeyError(f"Could not find asset price {assetId}")

        assetPrice = oraclePrice.price
        assetBalance = calcWithdrawReturn(fAssetBalance, depositInterestIndex)
        balanceValue = calcCollateralAssetLoanValue(assetBalance, assetPrice, ONE_4_DP)
        effectiveBalanceValue = calcCollateralAssetLoanValue(
            assetBalance, assetPrice, collateralFactor
        )

        totalCollateralBalanceValue += balanceValue
        totalEffectiveCollateralBalanceValue += effectiveBalanceValue
        netRate += balanceValue * depositInterestRate
        netYield += balanceValue * depositInterestYield

        collaterals.append(
            UserLoanInfoCollateral(
                poolAppId=poolAppId,
                assetId=assetId,
                assetPrice=assetPrice,
                collateralFactor=collateralFactor,
                depositInterestIndex=depositInterestIndex,
                fAssetBalance=fAssetBalance,
                assetBalance=assetBalance,
                balanceValue=balanceValue,
                effectiveBalanceValue=effectiveBalanceValue,
                interestRate=depositInterestRate,
                interestYield=depositInterestYield,
            )
        )

    # borrows
    borrows: list[UserLoanInfoBorrow] = []
    totalBorrowedAmountValue: int = 0
    totalBorrowBalanceValue: int = 0
    totalEffectiveBorrowBalanceValue: int = 0

    for brw in localState.borrows:
        poolAppId = brw.poolAppId
        borrowedAmount = brw.borrowedAmount
        oldBorrowBalance = brw.borrowBalance
        latestBorrowInterestIndex = brw.latestBorrowInterestIndex
        stableBorrowInterestRate = brw.stableBorrowInterestRate
        latestStableChange = brw.latestStableChange

        isBorPresent = oldBorrowBalance > 0
        if not isBorPresent:
            continue

        poolInfo = poolManagerPools[poolAppId]
        poolLoanInfo = loanPools[poolAppId]

        assetId = poolLoanInfo.assetId
        borrowFactor = poolLoanInfo.borrowFactor
        oraclePrice = prices[assetId]
        assetPrice = oraclePrice.price
        isStable = latestStableChange > 0

        if isStable:
            bii = calcBorrowInterestIndex(
                stableBorrowInterestRate, latestBorrowInterestIndex, latestStableChange
            )
            interestRate = stableBorrowInterestRate
            interestYield = compoundEverySecond(stableBorrowInterestRate, ONE_16_DP)
        else:
            bii = poolInfo.variableBorrowInterestIndex
            interestRate = poolInfo.variableBorrowInterestRate
            interestYield = poolInfo.variableBorrowInterestYield
        borrowedAmountValue = calcCollateralAssetLoanValue(
            borrowedAmount, oraclePrice.price, ONE_4_DP
        )  # no rounding
        borrowBalance = calcBorrowBalance(
            oldBorrowBalance, bii, latestBorrowInterestIndex
        )
        borrowBalanceValue = calcBorrowAssetLoanValue(
            borrowBalance, assetPrice, ONE_4_DP
        )
        effectiveBorrowBalanceValue = calcBorrowAssetLoanValue(
            borrowBalance, assetPrice, borrowFactor
        )

        totalBorrowedAmountValue += borrowedAmountValue
        totalBorrowBalanceValue += borrowBalanceValue
        totalEffectiveBorrowBalanceValue += effectiveBorrowBalanceValue
        netRate -= borrowBalanceValue * interestRate
        netYield -= borrowBalanceValue * interestYield

        borrows.append(
            UserLoanInfoBorrow(
                poolAppId=poolAppId,
                assetId=assetId,
                assetPrice=assetPrice,
                isStable=isStable,
                borrowFactor=borrowFactor,
                borrowedAmount=borrowedAmount,
                borrowedAmountValue=borrowedAmountValue,
                borrowBalance=borrowBalance,
                borrowBalanceValue=borrowBalanceValue,
                effectiveBorrowBalanceValue=effectiveBorrowBalanceValue,
                accruedInterest=borrowBalance - borrowedAmount,
                accruedInterestValue=borrowBalanceValue - borrowedAmountValue,
                interestRate=interestRate,
                interestYield=interestYield,
            )
        )

    if totalCollateralBalanceValue > 0:
        netRate //= totalCollateralBalanceValue
        netYield //= totalCollateralBalanceValue

    # combine
    return UserLoanInfo(
        userAddress=localState.userAddress,
        escrowAddress=localState.escrowAddress,
        collaterals=collaterals,
        borrows=borrows,
        netRate=netRate,
        netYield=netYield,
        totalCollateralBalanceValue=totalCollateralBalanceValue,
        totalBorrowedAmountValue=totalBorrowedAmountValue,
        totalBorrowBalanceValue=totalBorrowBalanceValue,
        totalEffectiveCollateralBalanceValue=totalEffectiveCollateralBalanceValue,
        totalEffectiveBorrowBalanceValue=totalEffectiveBorrowBalanceValue,
        loanToValueRatio=calcLTVRatio(
            totalBorrowBalanceValue, totalCollateralBalanceValue
        ),
        borrowUtilisationRatio=calcBorrowUtilisationRatio(
            totalEffectiveBorrowBalanceValue,
            totalEffectiveCollateralBalanceValue,
        ),
        liquidationMargin=calcLiquidationMargin(
            totalEffectiveBorrowBalanceValue, totalEffectiveCollateralBalanceValue
        ),
    )
