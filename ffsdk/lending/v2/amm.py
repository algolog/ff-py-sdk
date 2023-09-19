import json
from algosdk.v2client.indexer import IndexerClient
from urllib.request import urlopen
from ...state_utils import get_global_state, parse_uint64s
from .mathlib import compoundEveryHour, ONE_16_DP
from .datatypes import (
    LendingPoolInfo,
    PactLendingPool,
    PoolManagerInfo,
)


def retrievePactLendingPoolInfo(
    client: IndexerClient,
    lendingPool: PactLendingPool,
    poolManagerInfo: PoolManagerInfo,
) -> LendingPoolInfo:
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

    return LendingPoolInfo(
        fAsset0Supply=fa0s,
        asset0Supply=int(0),
        fAsset1Supply=fa1s,
        asset1Supply=int(0),
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
