from algosdk.v2client.indexer import IndexerClient
from algosdk.encoding import encode_as_bytes
from algosdk.transaction import Transaction, SuggestedParams
from algosdk.atomic_transaction_composer import AtomicTransactionComposer
from base64 import b64decode
from .datatypes import Oracle, OraclePrice, OraclePrices, LPToken
from .abi_contracts import oracleAdapterABIContract
from ..state_utils import get_global_state
from ..transaction_utils import sp_fee, signer, remove_signer_and_group


def parseOracleValue(base64Value: str) -> OraclePrice:
    value = b64decode(base64Value).hex()
    # [price (uint64), latest_update (uint64), ...]
    price = int(value[0:16], base=16)
    timestamp = int(value[16:32], base=16)
    return OraclePrice(price, timestamp)


def getOraclePrices(
    indexerClient: IndexerClient, oracle: Oracle, assetIds: list[int] = []
) -> OraclePrices:
    """
    Returns oracle prices for given oracle and provided assets.

    @param indexerClient - Algorand indexer client to query
    @param oracle - oracle to query
    @param assetIds - assets ids to get prices for, if undefined then returns all prices
    @returns OraclePrices oracle prices
    """
    oracle0AppId = oracle.oracle0AppId
    lpTokenOracle = oracle.lpTokenOracle

    oracleState = get_global_state(indexerClient, oracle0AppId, decode_byte_keys=False)
    if lpTokenOracle is None:
        lpTokenOracleState = {}
    else:
        lpTokenOracleState = get_global_state(indexerClient, lpTokenOracle)

    prices: OraclePrices = {}

    # get the assets for which we need to retrieve their prices
    allAssetIds = [
        int.from_bytes(k, byteorder="big")
        for k in (oracleState | lpTokenOracleState)
        if k not in [b"updater_addr", b"admin", b"tinyman_validator_app_id", b"td"]
    ]
    assets = assetIds if assetIds else allAssetIds

    # retrieve asset prices
    for assetId in assets:
        assetPrice = None
        if lpTokenOracle is None:
            lpTokenBase64Value = None
        else:
            lpTokenBase64Value = oracleState.get(encode_as_bytes(assetId))

        # lpTokenBase64Value defined iff asset is lp token in given lpTokenOracle
        if lpTokenBase64Value is not None:
            # TODO: translate this piece of code from js when oracle is actually available
            pass
        else:
            assetPrice = parseOracleValue(oracleState.get(encode_as_bytes(assetId)))

        prices[assetId] = assetPrice

    return prices


def prepareRefreshPricesInOracleAdapter(
    oracle: Oracle,
    userAddr: str,
    lpAssets: list[LPToken],
    baseAssetIds: list[int],
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to refresh the given assets.

    @param oracle - oracle applications to use
    @param userAddr - account address for the user
    @param lpAssets - list of lp assets
    @param baseAssetIds - list of base asset ids (non-lp assets)
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] refresh prices group transaction
    """
    oracleAdapterAppId = oracle.oracleAdapterAppId
    lpTokenOracle = oracle.lpTokenOracle
    oracle0AppId = oracle.oracle0AppId

    if len(lpAssets) > 0:
        raise ValueError("Refresh LP assets unsupported")

    atc = AtomicTransactionComposer()

    # prepare refresh prices arguments
    oracle1AppId = oracle.oracle1AppId if oracle.oracle1AppId else 0
    lpTokenOracleAppId = lpTokenOracle.appId if lpTokenOracle else 0
    lpAssetIds = [lpa.lpAssetId for lpa in lpAssets]

    # refresh prices
    atc.add_method_call(
        app_id=oracleAdapterAppId,
        method=oracleAdapterABIContract.get_method_by_name("refresh_prices"),
        sender=userAddr,
        sp=sp_fee(params, fee=1000),
        signer=signer,
        method_args=[
            lpAssetIds,
            baseAssetIds,
            oracle0AppId,
            oracle1AppId,
            lpTokenOracleAppId,
        ],
    )

    # build
    return remove_signer_and_group(atc.build_group())
