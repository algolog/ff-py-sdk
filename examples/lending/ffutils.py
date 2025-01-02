from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import Transaction, write_to_file, wait_for_confirmation
from ffsdk.lending.v2.datatypes import (
    Pool,
    LoanType,
    UserDepositFullInfo,
    UserDepositStakingInfo,
    UserLoanInfo,
)
from ffsdk.lending.v2.loan import getUserLoanAssets
from ffsdk.mathlib import ONE_4_DP, ONE_14_DP


def ask_sign_and_send(algod: AlgodClient, txn_group: list[Transaction], sk: str, extra_sign=None, simulate=False):
    """Ask user permission to proceed, sign and send transaction group.

    :param algod: Algod client
    :param txn_group: transaction group to sign and send
    :param sk: secret key for signing transactions
    :param extra_sign: dict[int, str], optional dictionary transaction_number->secret_key for
                       signing some of the transactions with another key(s)
    :param simulate: bool, simulate transactions instead of sending (default: False)
    """

    proceed_ask = input('Proceed (y/N)?: ').lower()
    do_proceed = True if proceed_ask in ['y', 'yes'] else False

    if do_proceed:
        print('Sending  transaction...')

        # Sign the group
        signed_txns = [txn.sign(sk) for txn in txn_group]
        if extra_sign is not None:
            for n in extra_sign:
                signed_txns[n] = signed_txns[n].transaction.sign(extra_sign[n])

        if simulate:
            res = algod.simulate_raw_transactions(signed_txns)
            rg0 = res["txn-groups"][0]
            print("Failed at:", rg0.get("failed-at"))
            print("Failure msg:", rg0.get("failure-message"))
        else:
            # Send
            try:
                txid = algod.send_transactions(signed_txns)
                wait_for_confirmation(algod, txid)
                print(f"Txid {txid} confirmed.")
            except Exception as e:
                print(e)


def user_deposit_report(udfi: UserDepositFullInfo, pools: dict[str, Pool]):
    pool_by_id = {pool.appId: name for name, pool in pools.items()}
    SEP = 91
    print(f"deposit escrow: {udfi.escrowAddress}")
    print("~" * SEP)
    print(
        "Market       APY%        fAssetBalance          Amount         assetBalance          $Value"
    )
    print("~" * SEP)
    for h in udfi.holdings:
        pool_name = pool_by_id[h.poolAppId]
        pool = pools[pool_name]
        value_usd = h.balanceValue / ONE_4_DP
        apy = h.interestYield / ONE_14_DP
        amount = h.assetBalance / 10**pool.assetDecimals
        print(
            f"{pool_name:8} {apy:8.2f} {h.fAssetBalance:20_} {amount:15.2f} {h.assetBalance:20_} {value_usd:15.2f}"
        )
    print("~" * SEP)


def user_staking_report(udsi: UserDepositStakingInfo, pools: dict[str, Pool]):
    pool_by_id = {pool.appId: name for name, pool in pools.items()}
    SEP = 111
    print(f"staking escrow: {udsi.escrowAddress}")
    print("~" * SEP)
    print(
        "Market   SI      APY%      fAssetBalance       assetBalance       Amount       $Value      Unclaimed      $Uncl"
    )
    print("~" * SEP)
    for stakeIndex, sp in enumerate(udsi.stakingPrograms):
        pool_name = pool_by_id[sp.poolAppId]
        pool = pools[pool_name]
        value_usd = sp.stakedAmountValue / ONE_4_DP
        deposit_yield = sp.depositInterestYield / ONE_14_DP
        amount = sp.assetStakedAmount / 10**pool.assetDecimals
        rewards_yield = sum(r.rewardInterestRate for r in sp.rewards) / ONE_14_DP
        total_yield = deposit_yield + rewards_yield
        unclaimed = " ".join(
            [f"{r.unclaimedReward:_}" for r in sp.rewards]
        )  # TODO: handle multiple rewardAssetId
        unclaimed_usd = sum(r.unclaimedRewardValue for r in sp.rewards) / ONE_4_DP
        print(
            f"{pool_name:8} {stakeIndex:2} {total_yield:9.2f} {sp.fAssetStakedAmount:18_} {sp.assetStakedAmount:18_} {amount:12.2f} {value_usd:12.2f} {unclaimed:>14} {unclaimed_usd:10.2f}"
        )
    print("~" * SEP)


def user_loan_report(loan: UserLoanInfo, ltype: LoanType, pools: dict[str, Pool]):
    pool_by_asset = {pool.assetId: name for name, pool in pools.items()}
    borrows_by_asset = {b.assetId: b for b in loan.borrows}
    collaterals_by_asset = {c.assetId: c for c in loan.collaterals}
    SEP = 91
    print(f"loan escrow: {loan.escrowAddress}  {ltype.name}")
    print("~" * SEP)
    print(
        "Market     Factor   Collateral_balance     $Collateral       Borrow_balance         $Borrow"
    )
    print("~" * SEP)
    # get assets in user loan
    lpAssets, baseAssetIds = getUserLoanAssets(pools, loan)
    if lpAssets:
        raise ValueError("LP assets are not supported in loans yet")

    for asset_id in baseAssetIds:
        sym = pool_by_asset[asset_id]
        collateral = collaterals_by_asset.get(asset_id, None)
        if collateral:
            factor = collateral.collateralFactor / ONE_4_DP
            collateral_balance = collateral.assetBalance
            collateral_usd = collateral.balanceValue / ONE_4_DP
        else:
            factor = 0
            collateral_balance = 0
            collateral_usd = 0

        borrow = borrows_by_asset.get(asset_id, None)
        if borrow:
            borrow_balance = borrow.borrowBalance  # borrow.borrowedAmount
            borrow_usd = borrow.effectiveBorrowBalanceValue / ONE_4_DP
        else:
            borrow_balance = 0
            borrow_usd = 0
        print(
                f"{sym:8} {factor:8.2f} {collateral_balance:20_} {collateral_usd:15.2f} {borrow_balance:20_} {borrow_usd:15.2f}"
        )
    print("~" * SEP)
    utilization = loan.borrowUtilisationRatio / ONE_4_DP
    sum_borrow_usd = loan.totalEffectiveBorrowBalanceValue / ONE_4_DP
    sum_max_borrow_usd = loan.totalEffectiveCollateralBalanceValue / ONE_4_DP

    print(f"Utilization: {sum_borrow_usd:.2f} / {sum_max_borrow_usd:.2f} = {utilization:.4f}")
