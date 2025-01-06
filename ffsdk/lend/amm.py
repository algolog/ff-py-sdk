import json
from algosdk.v2client.indexer import IndexerClient
from urllib.request import urlopen
from ..state_utils import get_global_state, get_local_state_at_app, parse_uint64s
from ..mathlib import compoundEveryHour, ONE_16_DP
from .datatypes import (
    PactLendingPool,
    PactLendingPoolInfo,
    PoolManagerInfo,
    TinymanLendingPool,
    TinymanLendingPoolInfo,
)


def retrievePactLendingPoolInfo(
    client: IndexerClient,
    lendingPool: PactLendingPool,
    poolManagerInfo: PoolManagerInfo,
) -> PactLendingPoolInfo:
    """
    Returns information regarding the given Pact lending pool.

    @param client - Algorand client to query
    @param lendingPool - Pact lending pool to query about
    @param poolManagerInfo - pool manager info which is returned by retrievePoolManagerInfo function
    @returns Promise<LendingPoolInfo> lending pool info
    """
    state = get_global_state(client, lendingPool.lpPoolAppId)

    config = parse_uint64s(state.get("CONFIG"))
    fa0s = int(state.get("A", 0))
    fa1s = int(state.get("B", 0))
    ltcs = int(state.get("L", 0))

    # pact pool swap fee interest
    with urlopen(f"https://api.pact.fi/api/pools/{lendingPool.lpPoolAppId}") as url:
        pactPoolData = json.load(url)
    swapFeeInterestRate = int(float(pactPoolData.get("apr_7d", 0)) * 1e16)
    tvlUsd = float(pactPoolData.get("tvl_usd", 0))

    # TODO: get farming APY from https://api.pact.fi/api/farms/all

    # lending pool deposit interest
    pool0 = poolManagerInfo.pools[lendingPool.pool0AppId]
    pool1 = poolManagerInfo.pools[lendingPool.pool1AppId]

    return PactLendingPoolInfo(
        fAsset0Supply=fa0s,
        fAsset1Supply=fa1s,
        liquidityTokenCirculatingSupply=ltcs,
        fee=config[2],
        swapFeeInterestRate=swapFeeInterestRate,
        swapFeeInterestYield=compoundEveryHour(swapFeeInterestRate, ONE_16_DP),
        asset0DepositInterestRate=pool0.depositInterestRate // 2,
        asset0DepositInterestYield=pool0.depositInterestYield // 2,
        asset1DepositInterestRate=pool1.depositInterestRate // 2,
        asset1DepositInterestYield=pool1.depositInterestYield // 2,
        tvlUsd=tvlUsd,
    )


def retrieveTinymanLendingPoolInfo(
    client: IndexerClient,
    tinymanAppId: int,
    lendingPool: TinymanLendingPool,
    poolManagerInfo: PoolManagerInfo,
) -> TinymanLendingPoolInfo:
    """
    Returns information regarding the given Tinyman lending pool.

    @param client - Algorand client to query
    @param tinymanAppId - Tinyman application id where lending pool belongs to
    @param lendingPool - Pact lending pool to query about
    @param poolManagerInfo - pool manager info which is returned by retrievePoolManagerInfo function
    @returns Promise<LendingPoolInfo> lending pool info
    """
    state = get_local_state_at_app(client, tinymanAppId, lendingPool.lpPoolAppAddress)

    if state is None:
        raise LookupError("Could not find lending pool")
    fee = state.get("total_fee_share", 0)
    fa0s = state.get("asset_2_reserves", 0)
    fa1s = state.get("asset_1_reserves", 0)
    ltcs = state.get("issued_pool_tokens", 0)

    # pool swap fee interest
    with urlopen(
        f"https://mainnet.analytics.tinyman.org/api/v1/pools/{lendingPool.lpPoolAppAddress}"
    ) as url:
        tmPoolData = json.load(url)

    swapFeeInterestRate = int(float(tmPoolData.get("annual_percentage_rate", 0)) * 1e16)
    swapFeeInterestYield = int(
        float(tmPoolData.get("annual_percentage_yield", 0)) * 1e16
    )
    farmInterestYield = int(
        float(tmPoolData.get("staking_total_annual_percentage_yield", 0)) * 1e16
    )
    tvlUsd = float(tmPoolData.get("liquidity_in_usd", 0))

    # lending pool deposit interest
    pool0 = poolManagerInfo.pools[lendingPool.pool0AppId]
    pool1 = poolManagerInfo.pools[lendingPool.pool1AppId]

    return TinymanLendingPoolInfo(
        fAsset0Supply=fa0s,
        fAsset1Supply=fa1s,
        liquidityTokenCirculatingSupply=ltcs,
        fee=fee,
        swapFeeInterestRate=swapFeeInterestRate,
        swapFeeInterestYield=swapFeeInterestYield,
        asset0DepositInterestRate=pool0.depositInterestRate // 2,
        asset0DepositInterestYield=pool0.depositInterestYield // 2,
        asset1DepositInterestRate=pool1.depositInterestRate // 2,
        asset1DepositInterestYield=pool1.depositInterestYield // 2,
        tvlUsd=tvlUsd,
        farmInterestYield=farmInterestYield,
    )
