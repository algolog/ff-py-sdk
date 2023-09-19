from base64 import b64decode
from algosdk.v2client.indexer import IndexerClient
from algosdk.transaction import (
    SuggestedParams,
    Transaction,
    OnComplete,
    ApplicationCloseOutTxn,
)
from algosdk.logic import get_application_address
from algosdk.account import generate_account
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from .mathlib import (
    ONE_16_DP,
    ONE_10_DP,
    UINT64,
    mulScale,
    compoundEveryHour,
    compoundEverySecond,
)
from .formulae import (
    calcBorrowInterestIndex,
    calcDepositInterestIndex,
    calcWithdrawReturn,
)
from .utils import getEscrows
from .oracle import getOraclePrices
from .abiContracts import depositsABIContract, poolABIContract
from ...transaction_utils import (
    signer,
    sp_fee,
    remove_signer_and_group,
    transferAlgoOrAsset,
    addEscrowNoteTransaction,
    removeEscrowNoteTransaction,
)
from ...state_utils import (
    get_global_state,
    get_balances,
    parse_uint64s,
    parse_bits_as_booleans,
)
from .datatypes import (
    Pool,
    PoolMetadataFromManager,
    PoolStateFromManager,
    PoolManagerInfo,
    PoolInfo_VariableBorrow,
    PoolInfo_StableBorrow,
    PoolInfo_Interest,
    PoolInfo_Caps,
    PoolInfo_Config,
    PoolInfo,
    UserDepositHolding,
    UserDepositInfo,
    UserDepositFullHolding,
    UserDepositFullInfo,
    Oracle,
    Account,
)


def retrievePoolManagerInfo(
    indexerClient: IndexerClient, poolManagerAppId: int
) -> PoolManagerInfo:
    """
    Returns information regarding the given pool manager.

    @param indexerClient - Algorand indexer client to query
    @param poolManagerAppId - pool manager application to query about
    @returns PoolManagerInfo - pool manager info
    """

    state = get_global_state(indexerClient, poolManagerAppId)
    pools = {}
    for i in range(63):
        poolBase64Value = state.get(i.to_bytes(1, "big").decode())
        poolValue = b64decode(poolBase64Value).hex()
        for j in range(3):
            basePos = j * 84
            try:
                poolAppId = int(poolValue[basePos : basePos + 12], base=16)
            except ValueError:
                poolAppId = -1

            # add pool
            if poolAppId > 0:
                vbir = int(poolValue[basePos + 12 : basePos + 28], base=16)
                vbiit1 = int(poolValue[basePos + 28 : basePos + 44], base=16)
                depir = int(poolValue[basePos + 44 : basePos + 60], base=16)
                diit1 = int(poolValue[basePos + 60 : basePos + 76], base=16)
                lu = int(poolValue[basePos + 76 : basePos + 84], base=16)

                vbii = calcBorrowInterestIndex(vbir, vbiit1, lu)
                dii = calcDepositInterestIndex(depir, diit1, lu)

                pools[poolAppId] = PoolStateFromManager(
                    variableBorrowInterestRate=vbir,
                    variableBorrowInterestYield=compoundEverySecond(vbir, ONE_16_DP),
                    variableBorrowInterestIndex=vbii,
                    depositInterestRate=depir,
                    depositInterestYield=compoundEveryHour(depir, ONE_16_DP),
                    depositInterestIndex=dii,
                    metadata=PoolMetadataFromManager(
                        oldVariableBorrowInterestIndex=vbiit1,
                        oldDepositInterestIndex=diit1,
                        oldTimestamp=lu,
                    ),
                )

    return PoolManagerInfo(pools)


def retrievePoolInfo(indexerClient: IndexerClient, pool: Pool) -> PoolInfo:
    """
    Returns information regarding the given pool.

    @param indexerClient - Algorand indexer client to query
    @param pool - pool application to query about
    @returns Promise<PoolInfo> pool info
    """

    state = get_global_state(indexerClient, pool.appId)

    varBor = parse_uint64s(state.get("v"))
    stblBor = parse_uint64s(state.get("s"))
    interest = parse_uint64s(state.get("i"))
    caps = parse_uint64s(state.get("ca"))
    config = parse_bits_as_booleans(state.get("co"))

    # combine
    return PoolInfo(
        variableBorrow=PoolInfo_VariableBorrow(
            vr0=varBor[0],
            vr1=varBor[1],
            vr2=varBor[2],
            totalVariableBorrowAmount=varBor[3],
            variableBorrowInterestRate=varBor[4],
            variableBorrowInterestYield=compoundEverySecond(varBor[4], ONE_16_DP),
            variableBorrowInterestIndex=calcBorrowInterestIndex(
                varBor[4], varBor[5], interest[6]
            ),
        ),
        stableBorrow=PoolInfo_StableBorrow(
            sr0=stblBor[0],
            sr1=stblBor[1],
            sr2=stblBor[2],
            sr3=stblBor[3],
            optimalStableToTotalDebtRatio=stblBor[4],
            rebalanceUpUtilisationRatio=stblBor[5],
            rebalanceUpDepositInterestRate=stblBor[6],
            rebalanceDownDelta=stblBor[7],
            totalStableBorrowAmount=stblBor[8],
            stableBorrowInterestRate=stblBor[9],
            stableBorrowInterestYield=compoundEverySecond(stblBor[9], ONE_16_DP),
            overallStableBorrowInterestAmount=stblBor[10] * UINT64 + stblBor[11],
        ),
        interest=PoolInfo_Interest(
            retentionRate=interest[0],
            flashLoanFee=interest[1],
            optimalUtilisationRatio=interest[2],
            totalDeposits=interest[3],
            depositInterestRate=interest[4],
            depositInterestYield=compoundEveryHour(interest[4], ONE_16_DP),
            depositInterestIndex=calcDepositInterestIndex(
                interest[4], interest[5], interest[6]
            ),
            latestUpdate=interest[6],
        ),
        caps=PoolInfo_Caps(
            borrowCap=caps[0],
            stableBorrowPercentageCap=caps[1],
        ),
        config=PoolInfo_Config(
            depreciated=config[0],
            rewardsPaused=config[1],
            stableBorrowSupported=config[2],
            flashLoanSupported=config[3],
        ),
    )


def retrieveUserDepositsInfo(
    indexerClient: IndexerClient,
    depositsAppId: int,
    userAddr: str,
) -> list[UserDepositInfo]:
    """
    Returns basic information regarding the given user's deposit escrows.

    @param indexerClient - Algorand indexer client to query
    @param depositsAppId - deposits application to query about
    @param userAddr - account address for the user
    @returns Promise<UserDepositInfo[]> user deposits info
    """
    userDepositsInfo: list[UserDepositInfo] = []

    # get users' escrows
    escrows = getEscrows(indexerClient, userAddr, depositsAppId, "da ", "dr ")

    # get all remaining escrows' holdings
    for escrowAddr in escrows:
        assetHoldings = get_balances(indexerClient, escrowAddr)
        holdings: list[UserDepositHolding] = [
            UserDepositHolding(fAssetId=asset_id, fAssetBalance=assetHoldings[asset_id])
            for asset_id in sorted(assetHoldings)
            if asset_id != 0
        ]
        userDepositsInfo.append(UserDepositInfo(escrowAddr, holdings))

    return userDepositsInfo


def retrieveUserDepositsFullInfo(
    indexerClient: IndexerClient,
    poolManagerAppId: int,
    depositsAppId: int,
    pools: dict[str, Pool],
    oracle: Oracle,
    userDepositsInfo: list[UserDepositInfo],
) -> list[UserDepositFullInfo]:
    """
    Returns full information regarding the given user's deposit escrows.

    @param indexerClient - Algorand indexer client to query
    @param poolManagerAppId - pool manager application to query about
    @param depositsAppId - deposits application to query about
    @param pools - pools in pool manager (either MainnetPools or TestnetPools)
    @param oracle - oracle to query
    @param userDepositsInfo - user deposits info which is returned by retrieveUserDepositsInfo function
    @returns Promise<UserDepositFullInfo[]> user deposits full info
    """
    # get all prerequisites
    poolManagerInfo = retrievePoolManagerInfo(indexerClient, poolManagerAppId)
    prices = getOraclePrices(indexerClient, oracle)

    # map from UserDepositInfo to ExtendedUserDepositInfo
    full_infos = []
    for deposit in userDepositsInfo:
        full_holdings = []
        for hld in deposit.holdings:
            fAssetId, fAssetBalance = hld.fAssetId, hld.fAssetBalance
            # filter out ALGO escrow holding
            if fAssetId == 0:
                continue
            matching_pools = [p for p in pools.values() if p.fAssetId == fAssetId]
            if len(matching_pools) != 1:
                raise ValueError(f"Error finding pool with fAsset {fAssetId}")
            else:
                pool = matching_pools[0]

            poolAppId = pool.appId
            assetId = pool.assetId
            poolInfo = poolManagerInfo.pools[poolAppId]
            depositInterestIndex = poolInfo.depositInterestIndex
            depositInterestRate = poolInfo.depositInterestRate
            depositInterestYield = poolInfo.depositInterestYield

            oraclePrice = prices[assetId]
            assetPrice = oraclePrice.price
            assetBalance = calcWithdrawReturn(fAssetBalance, depositInterestIndex)
            balanceValue = mulScale(assetBalance, assetPrice, ONE_10_DP)  # 4 d.p.

            full_holdings.append(
                UserDepositFullHolding(
                    fAssetId,
                    fAssetBalance,
                    poolAppId,
                    assetId,
                    assetPrice,
                    assetBalance,
                    balanceValue,
                    interestRate=depositInterestRate,
                    interestYield=depositInterestYield,
                )
            )
        full_infos.append(UserDepositFullInfo(deposit.escrowAddress, full_holdings))

    return full_infos


def retrieveUserDepositInfo(
    indexerClient: IndexerClient, escrowAddr: str
) -> UserDepositInfo:
    """
    Returns information regarding the given user's deposit escrows.

    @param indexerClient - Algorand indexer client to query
    @param depositsAppId - deposits application to query about
    @param escrowAddr - account address for the deposit escrow
    @returns Promise<UserDepositInfo> user deposit info
    """
    assetHoldings = get_balances(indexerClient, escrowAddr)
    holdings = [
        UserDepositHolding(fAssetId=asset_id, fAssetBalance=assetHoldings[asset_id])
        for asset_id in sorted(assetHoldings)
        if asset_id != 0
    ]

    return UserDepositInfo(escrowAddr, holdings)


def prepareAddDepositEscrowToDeposits(
    depositsAppId: int,
    userAddr: str,
    params: SuggestedParams,
) -> tuple[list[Transaction], Account]:
    """
    Returns a group transaction to add escrow before depositing.

    @param depositsAppId - deposits application to add an escrow for
    @param userAddr - account address for the user
    @param params - suggested params for the transactions with the fees overwritten
    @returns { txns: Transaction[], escrow: Account } object containing group transaction and generated escrow account
    """
    key, address = generate_account()
    escrow = Account(addr=address, sk=key)

    userCall = addEscrowNoteTransaction(
        userAddr, escrow.addr, depositsAppId, "da ", sp_fee(params, fee=2000)
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=escrow.addr,
        signer=signer,
        app_id=depositsAppId,
        on_complete=OnComplete.OptInOC,
        method=depositsABIContract.get_method_by_name("add_deposit_escrow"),
        method_args=[TransactionWithSigner(userCall, signer)],
        rekey_to=get_application_address(depositsAppId),
        sp=sp_fee(params, fee=0),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns, escrow


def prepareOptDepositEscrowIntoAssetInDeposits(
    depositsAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to opt deposits escrow into asset so that it can hold a given pool's f asset.

    @param depositsAppId - deposits application of escrow
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit escrow
    @param pool - pool to add f asset of
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction opt deposit escrow into asset transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId
    poolManagerIndex = pool.poolManagerIndex

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositsAppId,
        method=depositsABIContract.get_method_by_name("opt_escrow_into_asset"),
        method_args=[
            escrowAddr,
            poolManagerAppId,
            poolAppId,
            fAssetId,
            poolManagerIndex,
        ],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareDepositIntoPool(
    pool: Pool,
    poolManagerAppId: int,
    userAddr: str,
    receiverAddr: str,
    assetAmount: int,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a transaction to deposit asset into given pool.

    @param pool - pool application to deposit into
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param receiverAddr - account address to receive the deposit (typically the user's deposit escrow or loan escrow)
    @param assetAmount - the asset amount to deposit
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] deposit asset group transaction
    """
    appId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId

    sendAsset = transferAlgoOrAsset(
        assetId,
        userAddr,
        get_application_address(appId),
        assetAmount,
        sp_fee(params, fee=0),
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=appId,
        method=poolABIContract.get_method_by_name("deposit"),
        method_args=[
            TransactionWithSigner(sendAsset, signer),
            receiverAddr,
            assetId,
            fAssetId,
            poolManagerAppId,
        ],
        sp=sp_fee(params, fee=4000),
    )
    return remove_signer_and_group(atc.build_group())


def prepareWithdrawFromDepositEscrowInDeposits(
    depositsAppId: int,
    pool: Pool,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    amount: int,
    isfAssetAmount: bool,
    remainDeposited: bool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to withdraw from a deposits escrow

    @param depositsAppId - deposits application of escrow
    @param pool - pool to withdraw from
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit escrow
    @param receiverAddr - account address to receive the withdrawal (typically the same as the user address)
    @param amount - the amount of asset / f asset to send to withdraw from escrow.
    @param isfAssetAmount - whether the amount to withdraw is expressed in terms of f asset or asset
    @param remainDeposited - whether receiver should get f asset or asset (cannot remain deposited and use asset amount)
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction withdraw from deposit escrow transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId
    poolManagerIndex = pool.poolManagerIndex

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositsAppId,
        method=depositsABIContract.get_method_by_name("withdraw"),
        method_args=[
            escrowAddr,
            receiverAddr,
            poolManagerAppId,
            poolAppId,
            assetId,
            fAssetId,
            amount,
            isfAssetAmount,
            remainDeposited,
            poolManagerIndex,
        ],
        sp=sp_fee(params, fee=2000 if remainDeposited else 6000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareWithdrawFromPool(
    pool: Pool,
    poolManagerAppId: int,
    userAddr: str,
    receiverAddr: str,
    fAssetAmount: int,
    receivedAssetAmount: int,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to withdraw from a user's wallet

    @param pool - pool to withdraw from
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param receiverAddr - account address to receive the withdrawal (typically the same as the user address)
    @param fAssetAmount - the amount of f asset to send to the pool
    @param receivedAssetAmount - the amount of asset to receive. Any excess f asset sent will be returned to the deposit escrow. If zero then interpreted as variable withdrawal.
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] withdraw from user's wallet group transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId

    sendfAsset = transferAlgoOrAsset(
        fAssetId,
        userAddr,
        get_application_address(poolAppId),
        fAssetAmount,
        sp_fee(params, fee=0),
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=poolAppId,
        method=poolABIContract.get_method_by_name("withdraw"),
        method_args=[
            TransactionWithSigner(sendfAsset, signer),
            receivedAssetAmount,
            receiverAddr,
            assetId,
            fAssetId,
            poolManagerAppId,
        ],
        sp=sp_fee(params, fee=5000),
    )

    return remove_signer_and_group(atc.build_group())


def prepareUpdatePoolInterestIndexes(
    pool: Pool,
    poolManagerAppId: int,
    userAddr: str,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to update a pool's interest indexes

    @param pool - pool to update
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] update pool's interest indexes transaction
    """
    appId = pool.appId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=appId,
        method=poolABIContract.get_method_by_name("update_pool_interest_indexes"),
        method_args=[poolManagerAppId],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareOptOutDepositEscrowFromAssetInDeposits(
    depositsAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to remove asset from deposit escrow

    @param depositsAppId - deposits application of escrow
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit escrow
    @param pool - pool to remove f asset of
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction opt out deposit escrow from asset transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositsAppId,
        method=depositsABIContract.get_method_by_name("close_out_escrow_from_asset"),
        method_args=[escrowAddr, get_application_address(poolAppId), fAssetId],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareRemoveDepositEscrowFromDeposits(
    depositsAppId: int,
    userAddr: str,
    escrowAddr: str,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to remove a user's deposit escrow and return its minimum balance to the user.

    @param depositsAppId - deposits application of escrow
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit escrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] remove and close out deposit escrow group transaction
    """
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositsAppId,
        method=depositsABIContract.get_method_by_name("remove_deposit_escrow"),
        method_args=[escrowAddr],
        sp=sp_fee(params, fee=4000),
    )
    txns = remove_signer_and_group(atc.build_group())
    optOutTx = ApplicationCloseOutTxn(escrowAddr, sp_fee(params, fee=0), depositsAppId)
    closeToTx = removeEscrowNoteTransaction(
        escrowAddr, userAddr, "dr ", sp_fee(params, fee=0)
    )
    return [txns[0], optOutTx, closeToTx]
