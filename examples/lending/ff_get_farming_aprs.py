from algosdk.v2client.algod import AlgodClient
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.client import FFMainnetClient
from ffsdk.lending.v2.constants.mainnet_constants import MainnetPactLPFarms
from ffsdk.lending.v2.deposit import retrievePoolManagerInfo, retrievePoolInfo
from ffsdk.lending.v2.depositStaking import retrieveDepositStakingInfo
from ffsdk.lending.v2.formulae import calcWithdrawReturn
from ffsdk.lending.v2.mathlib import ONE_14_DP, SECONDS_IN_YEAR
from ffsdk.lending.v2.utils import depositStakingProgramsInfo
from ffsdk.lending.v2.oracle import getOraclePrices
import pactsdk

ONE_6_DP = 1e6
ONE_8_DP = 1e8


algod_address = "http://127.0.0.1:8080"
algod_token = open("/var/lib/algorand/algod.token", "r").read()
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, None, None)
client = FFMainnetClient(algod, indexer).lending
pact = pactsdk.PactClient(algod)

pmi = retrievePoolManagerInfo(client.indexer, client.pool_manager_app_id)
dsi = retrieveDepositStakingInfo(client.indexer, client.deposit_staking_app_id)

oracle_prices = getOraclePrices(client.indexer, client.oracle)
dpi = depositStakingProgramsInfo(dsi, pmi, client.pools, oracle_prices)
pool_deposit_staking_info = {dspi.poolAppId: dspi for dspi in dpi}
pools_by_asset = {pool.assetId: pool for name, pool in client.pools.items()}

print("~" * 45)
print("Market              APR%     Total deposit($)")
print("~" * 45)

# FolksFinance deposit staking programs
for market_name, pool in client.pools.items():
    pool_info = retrievePoolInfo(client.indexer, pool)
    total_deposits = pool_info.interest.totalDeposits / ONE_6_DP
    usd_deposits = oracle_prices[pool.assetId].price * total_deposits / ONE_8_DP
    deposit_yield = pool_info.interest.depositInterestYield / ONE_14_DP
    if pool.appId in pool_deposit_staking_info:
        rewards = pool_deposit_staking_info[pool.appId].rewards
        rewards_yield = sum(r.rewardInterestRate for r in rewards) / ONE_14_DP
    else:
        rewards_yield = 0
    total_yield = deposit_yield + rewards_yield

    print(f"{market_name:17} {total_yield:6.2f} {int(usd_deposits):19_}")


# Pact farming programs
for lpname, lp in client.lending_pools.items():
    # pact fAssets amm pool
    pp = pact.fetch_pool_by_id(lp.lpPoolAppId)
    # calc total value stored in pact pool
    if pools_by_asset[lp.asset0Id].fAssetId == pp.primary_asset.index:
        total_fAsset0, total_fAsset1 = pp.state.total_primary, pp.state.total_secondary
    else:
        total_fAsset0, total_fAsset1 = pp.state.total_secondary, pp.state.total_primary

    pool0Info = pmi.pools[lp.pool0AppId]
    pool1Info = pmi.pools[lp.pool1AppId]
    pp_value0_usd = (
        calcWithdrawReturn(total_fAsset0, pool0Info.depositInterestIndex)
        * oracle_prices[lp.asset0Id].price
        / ONE_14_DP
    )
    pp_value1_usd = (
        calcWithdrawReturn(total_fAsset1, pool1Info.depositInterestIndex)
        * oracle_prices[lp.asset1Id].price
        / ONE_14_DP
    )
    pp_tvl_usd = pp_value0_usd + pp_value1_usd

    # farm on-chain info
    farm_name = f"{pp.primary_asset.unit_name}/{pp.secondary_asset.unit_name}"
    farm_app_id = MainnetPactLPFarms[lpname]
    pf = pact.farming.fetch_farm_by_id(farm_app_id)
    farm_tvl_usd = pp_tvl_usd * pf.state.total_staked / pp.state.total_liquidity

    # rewards per second in usd terms
    rps_usd = sum(
        rps * oracle_prices[asset.index].price / ONE_14_DP
        for asset, rps in pf.state.rewards_per_second.items()
    ) if pf.state.duration else 0
    farm_apr = 100 * rps_usd * SECONDS_IN_YEAR / farm_tvl_usd

    # lending apr
    lend_apr = (
        pmi.pools[lp.pool0AppId].depositInterestYield
        + pmi.pools[lp.pool1AppId].depositInterestYield
    ) / (2 * ONE_14_DP)

    swap_apr = 0  # TODO (no on-chain data available)
    total_apr = farm_apr + lend_apr + swap_apr

    print(f"{farm_name:17} {total_apr:6.2f} {int(farm_tvl_usd):19_}")

print("~" * 45)
