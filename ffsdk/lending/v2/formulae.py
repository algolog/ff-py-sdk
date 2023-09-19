from time import time
from .mathlib import (
    divScale,
    divScaleRoundUp,
    expBySquaring,
    mulScale,
    mulScaleRoundUp,
    ONE_10_DP,
    ONE_14_DP,
    ONE_16_DP,
    ONE_4_DP,
    SECONDS_IN_YEAR,
    sqrt,
)


def calcAssetDollarValue(amount: int, price: int) -> int:
    """
    Calculates the dollar value of a given asset amount
    @param amount (0dp)
    @param price (14dp)
    @return value (0dp)
    """
    return mulScaleRoundUp(amount, price, ONE_14_DP)


def calcTotalDebt(totalVarDebt: int, totalStblDebt: int) -> int:
    """
    Calculates the total debt of a pool
    @param totalVarDebt (0dp)
    @param totalStblDebt (0dp)
    @return totalDebt (0dp)
    """
    return totalVarDebt + totalStblDebt


def calcAvailableLiquidity(totalDebt: int, totalDeposits: int) -> int:
    """
    Calculates the total debt of a pool
    @param totalDebt (0dp)
    @param totalDeposits (0dp)
    @return availableLiquidity (0dp)
    """
    return totalDeposits - totalDebt


def calcStableBorrowRatio(stblBorAmount: int, availableLiquidity: int) -> int:
    """
    Calculates the ratio of the available liquidity that is being stable borrowed
    @param stblBorAmount (0dp)
    @param availableLiquidity (0dp)
    @return stableBorrowRatio (16dp)
    """
    return divScale(stblBorAmount, availableLiquidity, ONE_16_DP)


def calcMaxSingleStableBorrow(availableLiquidity: int, sbpc: int) -> int:
    """
    Calculates the maximum stable borrow amount a user can make in one go
    @param availableLiquidity (0dp)
    @param sbpc (0dp)
    @return stableBorrowRatio (16dp)
    """
    return mulScale(availableLiquidity, sbpc, ONE_16_DP)


def calcUtilisationRatio(totalDebt: int, totalDeposits: int) -> int:
    """
    Calculates the utilisation ratio of a pool
    @param totalDebt (0dp)
    @param totalDeposits (0dp)
    @return utilisationRatio (16dp)
    """
    if totalDeposits == 0:
        return 0
    return divScale(totalDebt, totalDeposits, ONE_16_DP)


def calcStableDebtToTotalDebtRatio(totalStblDebt: int, totalDebt: int) -> int:
    """
    Calculates the stable debt to total debt ratio of a pool
    @param totalStblDebt (0dp)
    @param totalDebt (0dp)
    @return stableDebtToTotalDebtRatio (16dp)
    """
    if totalDebt == 0:
        return 0
    return divScale(totalStblDebt, totalDebt, ONE_16_DP)


def calcVariableBorrowInterestRate(
    vr0: int, vr1: int, vr2: int, ut: int, uopt: int
) -> int:
    """
    Calculate the variable borrow interest rate of a pool
    @param vr0 (16dp)
    @param vr1 (16dp)
    @param vr2 (16dp)
    @param ut (16dp)
    @param uopt (16dp)
    @return variableBorrowInterestRate (16dp)
    """
    if ut < uopt:
        return vr0 + divScale(mulScale(ut, vr1, ONE_16_DP), uopt, ONE_16_DP)
    else:
        return (
            vr0
            + vr1
            + divScale(mulScale(ut - uopt, vr2, ONE_16_DP), ONE_16_DP - uopt, ONE_16_DP)
        )


def calcStableBorrowInterestRate(
    vr1: int,
    sr0: int,
    sr1: int,
    sr2: int,
    sr3: int,
    ut: int,
    uopt: int,
    ratiot: int,
    ratioopt: int,
) -> int:
    """
    Calculate the stable borrow interest rate of a pool
    @param vr1 (16dp)
    @param sr0 (16dp)
    @param sr1 (16dp)
    @param sr2 (16dp)
    @param sr3 (16dp)
    @param ut (16dp)
    @param uopt (16dp)
    @param ratiot (16dp)
    @param ratioopt (16dp)
    @return stableBorrowInterestRate (16dp)
    """
    if ut <= uopt:
        base = vr1 + sr0 + divScale(mulScale(ut, sr1, ONE_16_DP), uopt, ONE_16_DP)
    else:
        base = (
            vr1
            + sr0
            + sr1
            + divScale(mulScale(ut - uopt, sr2, ONE_16_DP), ONE_16_DP - uopt, ONE_16_DP)
        )

    if ratiot <= ratioopt:
        extra = 0
    else:
        extra = divScale(
            mulScale(sr3, ratiot - ratioopt, ONE_16_DP), ONE_16_DP - ratioopt, ONE_16_DP
        )
    return base + extra


def calcOverallBorrowInterestRate(
    totalVarDebt: int, totalDebt: int, vbirt: int, osbiat: int
) -> int:
    """
    Calculate the overall borrow interest rate of a pool
    @param totalVarDebt (0dp)
    @param totalDebt (0dp)
    @param vbirt (16dp)
    @param osbiat (16dp)
    @return overallBorrowInterestRate (16dp)
    """
    if totalDebt == 0:
        return 0
    return (totalVarDebt * vbirt + osbiat) // totalDebt


def calcDepositInterestRate(obirt: int, rr: int, ut: int) -> int:
    """
    Calculate the deposit interest rate of a pool
    @param obirt (16dp)
    @param ut (16dp)
    @param rr (16dp)
    @return overallBorrowInterestRate (16dp)
    """
    return mulScale(mulScale(ut, obirt, ONE_16_DP), ONE_16_DP - rr, ONE_16_DP)


def calcBorrowInterestIndex(birt1: int, biit1: int, latestUpdate: int) -> int:
    """
    Calculate the borrow interest index of pool
    @param birt1 (16dp)
    @param biit1 (16dp)
    @param latestUpdate (0dp)
    @return borrowInterestIndex (14dp)
    """
    dt = int(time()) - latestUpdate
    return mulScale(
        biit1,
        expBySquaring(ONE_16_DP + birt1 // SECONDS_IN_YEAR, dt, ONE_16_DP),
        ONE_16_DP,
    )


def calcDepositInterestIndex(dirt1: int, diit1: int, latestUpdate: int) -> int:
    """
    Calculate the deposit interest index of pool
    @param dirt1 (16dp)
    @param diit1 (16dp)
    @param latestUpdate (0dp)
    @return depositInterestIndex (14dp)
    """
    dt = int(time()) - latestUpdate
    return mulScale(diit1, ONE_16_DP + (dirt1 * dt) // SECONDS_IN_YEAR, ONE_16_DP)


def calcDepositReturn(depositAmount: int, diit: int) -> int:
    """
    Calculates the fAsset received from a deposit
    @param depositAmount (0dp)
    @param diit (14dp)
    @return depositReturn (0dp)
    """
    return divScale(depositAmount, diit, ONE_14_DP)


def calcWithdrawReturn(withdrawAmount: int, diit: int) -> int:
    """
    Calculates the asset received from a withdraw
    @param withdrawAmount (0dp)
    @param diit (14dp)
    @return withdrawReturn (0dp)
    """
    return mulScale(withdrawAmount, diit, ONE_14_DP)


def calcCollateralAssetLoanValue(amount: int, price: int, factor: int) -> int:
    """
    Calculates the collateral asset loan value
    @param amount (0dp)
    @param price (14dp)
    @param factor (4dp)
    @return loanValue (4dp)
    """
    return mulScale(mulScale(amount, price, ONE_10_DP), factor, ONE_4_DP)


def calcBorrowAssetLoanValue(amount: int, price: int, factor: int) -> int:
    """
    Calculates the borrow asset loan value
    @param amount (0dp)
    @param price (14dp)
    @param factor (4dp)
    @return loanValue (4dp)
    """
    return mulScaleRoundUp(mulScaleRoundUp(amount, price, ONE_10_DP), factor, ONE_4_DP)


def calcLTVRatio(totalBorrowBalanceValue: int, totalCollateralBalanceValue: int) -> int:
    """
    Calculates the loan's LTV ratio
    @param totalBorrowBalanceValue (4dp)
    @param totalCollateralBalanceValue (4dp)
    @return LTVRatio (4dp)
    """
    if totalCollateralBalanceValue == 0:
        return 0
    return divScale(totalBorrowBalanceValue, totalCollateralBalanceValue, ONE_4_DP)


def calcBorrowUtilisationRatio(
    totalEffectiveBorrowBalanceValue: int,
    totalEffectiveCollateralBalanceValue: int,
) -> int:
    """
    Calculates the loan's borrow utilisation ratio
    @param totalEffectiveBorrowBalanceValue (4dp)
    @param totalEffectiveCollateralBalanceValue (4dp)
    @return borrowUtilisationRatio (4dp)
    """
    if totalEffectiveCollateralBalanceValue == 0:
        return 0
    return divScale(
        totalEffectiveBorrowBalanceValue, totalEffectiveCollateralBalanceValue, ONE_4_DP
    )


def calcLiquidationMargin(
    totalEffectiveBorrowBalanceValue: int,
    totalEffectiveCollateralBalanceValue: int,
) -> int:
    """
    Calculates the loan's liquidation margin
    @param totalEffectiveBorrowBalanceValue (4dp)
    @param totalEffectiveCollateralBalanceValue (4dp)
    @return liquidationMargin (4dp)
    """
    if totalEffectiveCollateralBalanceValue == 0:
        return 0
    return divScale(
        totalEffectiveCollateralBalanceValue - totalEffectiveBorrowBalanceValue,
        totalEffectiveCollateralBalanceValue,
        ONE_4_DP,
    )


def calcBorrowBalance(bbtn1: int, biit: int, biitn1: int) -> int:
    """
    Calculates the borrow balance of the loan at time t
    @param bbtn1 (0dp)
    @param biit (14dp)
    @param biitn1 (14dp)
    @return borrowBalance (0dp)
    """
    return mulScaleRoundUp(bbtn1, divScaleRoundUp(biit, biitn1, ONE_14_DP), ONE_14_DP)


def calcLoanStableInterestRate(bbt: int, amount: int, sbirtn1: int, sbirt1: int) -> int:
    """
    Calculates the stable borrow interest rate of the loan after a borrow increase
    @param bbt (0dp)
    @param amount (0dp)
    @param sbirtn1 (16dp)
    @param sbirt1 (16dp)
    @return stableInterestRate (16dp)
    """
    return (bbt * sbirtn1 + amount * sbirt1) // (bbt + amount)


def calcRebalanceUpThreshold(rudir: int, vr0: int, vr1: int, vr2: int) -> int:
    """
    Calculates the deposit interest rate condition required to rebalance up stable borrow.
    Note that there is also a second condition on the pool utilisation ratio.
    @param rudir (16dp)
    @param vr0 (16dp)
    @param vr1 (16dp)
    @param vr2 (16dp)
    @return rebalanceUpThreshold (16dp)
    """
    return mulScale(rudir, vr0 + vr1 + vr2, ONE_16_DP)


def calcRebalanceDownThreshold(rdd: int, sbirt1: int) -> int:
    """
    Calculates the stable interest rate condition required to rebalance down stable borrow
    @param rdd (16dp)
    @param sbirt1 (16dp)
    @return rebalanceDownThreshold (16dp)
    """
    return mulScale(ONE_16_DP + rdd, sbirt1, ONE_16_DP)


def calcFlashLoanRepayment(borrowAmount: int, fee: int) -> int:
    """
    Calculates the flash loan repayment amount for a given borrow amount and fee
    @param borrowAmount (0dp)
    @param fee (16dp)
    @return repaymentAmount (0dp)
    """
    return borrowAmount + mulScaleRoundUp(borrowAmount, fee, ONE_16_DP)


def calcLPPrice(r0: int, r1: int, p0: int, p1: int, lts: int) -> int:
    """
    Calculates the LP price
    @param r0 pool supply of asset 0
    @param r1 pool supply of asset 1
    @param p0 price of asset 0
    @param p1 price of asset 1
    @param lts circulating supply of liquidity token
    @return bigint LP price
    """
    return 2 * (sqrt(r0 * p0 * r1 * p1) // lts)
