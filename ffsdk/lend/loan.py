from base64 import b64decode
from algosdk.v2client.indexer import IndexerClient
from algosdk.transaction import (
    SuggestedParams,
    Transaction,
    OnComplete,
    ApplicationCloseOutTxn,
)
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk.logic import get_application_address
from algosdk.account import generate_account
from algosdk.encoding import encode_address
from .utils import getEscrows, loanLocalState, userLoanInfo
from ..mathlib import divScale, mulScale, ONE_4_DP, ONE_10_DP
from .formulae import (
    calcBorrowUtilisationRatio,
    calcDepositReturn,
    calcFlashLoanRepayment,
)
from .deposit import retrievePoolManagerInfo
from .oracle import getOraclePrices, prepareRefreshPricesInOracleAdapter
from .abi_contracts import loanABIContract, poolABIContract
from ..transaction_utils import (
    signer,
    sp_fee,
    remove_signer_and_group,
    transferAlgoOrAsset,
    addEscrowNoteTransaction,
    removeEscrowNoteTransaction,
)
from ..state_utils import (
    get_global_state,
    get_local_state_at_app,
    format_state,
)
from .datatypes import (
    AssetsAdditionalInterest,
    LoanInfo,
    PoolLoanInfo,
    LoanLocalState,
    LPToken,
    UserLoanInfo,
    Oracle,
    OraclePrices,
    Pool,
    PoolManagerInfo,
    Account,
)


def retrieveLoanInfo(client: IndexerClient, loanAppId: int) -> LoanInfo:
    """
    Returns information regarding the given pool.

    @param client - Algorand client to query
    @param loanAppId - loan application to query about
    @returns Promise<LoanInfo[]> loan info
    """
    state = get_global_state(client, loanAppId)

    paramsBase64Value = state.get("pa")
    paramsValue = b64decode(paramsBase64Value).hex()
    adminAddress = encode_address(b64decode(paramsBase64Value)[0:32])
    poolManagerAppId = int(paramsValue[64:80], base=16)
    oracleAdapterAppId = int(paramsValue[80:96], base=16)
    canSwapCollateral = bool(int(paramsValue[96:98], base=16))

    pools: dict[int, PoolLoanInfo] = {}
    for i in range(63):
        poolBase64Value = state.get(f"{i:c}")
        poolValue = b64decode(poolBase64Value).hex()

        for j in range(3):
            basePos = j * 84
            poolAppId = int(poolValue[basePos : basePos + 16], base=16)
            # add pool
            if poolAppId > 0:
                pools[poolAppId] = PoolLoanInfo(
                    poolAppId=poolAppId,
                    assetId=int(poolValue[basePos + 16 : basePos + 32], base=16),
                    collateralCap=int(poolValue[basePos + 32 : basePos + 48], base=16),
                    collateralUsed=int(poolValue[basePos + 48 : basePos + 64], base=16),
                    collateralFactor=int(
                        poolValue[basePos + 64 : basePos + 68], base=16
                    ),
                    borrowFactor=int(poolValue[basePos + 68 : basePos + 72], base=16),
                    liquidationMax=int(poolValue[basePos + 72 : basePos + 76], base=16),
                    liquidationBonus=int(
                        poolValue[basePos + 76 : basePos + 80], base=16
                    ),
                    liquidationFee=int(poolValue[basePos + 80 : basePos + 84], base=16),
                )

    # combine
    return LoanInfo(
        adminAddress, poolManagerAppId, oracleAdapterAppId, canSwapCollateral, pools
    )


def retrieveLoansLocalState(
    indexerClient: IndexerClient,
    loanAppId: int,
    userAddr: str,
) -> list[LoanLocalState]:
    """
    Returns local state regarding the loan escrows of a given user.
    Use for advanced use cases where optimising number of network request.

    @param indexerClient - Algorand indexer client to query
    @param loanAppId - loan application to query about
    @param userAddr - account address for the user
    @returns Promise<LoanLocalState[]> loan escrows' local state
    """
    loansLocalState: list[LoanLocalState] = []

    escrows = getEscrows(indexerClient, userAddr, loanAppId, "la ", "lr ")

    # get all remaining loans' local state
    for escrowAddr in escrows:
        state = get_local_state_at_app(indexerClient, loanAppId, escrowAddr)
        if state is None:
            raise LookupError(f"Could not find loan {loanAppId} in escrow {escrowAddr}")
        loansLocalState.append(loanLocalState(state, loanAppId, escrowAddr))

    return loansLocalState


def retrieveLoanLocalState(
    client: IndexerClient,
    loanAppId: int,
    escrowAddr: str,
) -> LoanLocalState:
    """
    Returns local state of given escrow.
    Use for advanced use cases where optimising number of network request.

    @param client - Algorand indexer client to query
    @param loanAppId - loan application to query about
    @param escrowAddr - account address for the loan escrow
    @returns Promise<LoanLocalState> loan escrow local state
    """
    state = get_local_state_at_app(client, loanAppId, escrowAddr)
    if state is None:
        raise LookupError(f"Could not find loan {loanAppId} in escrow {escrowAddr}")
    return loanLocalState(state, loanAppId, escrowAddr)


def retrieveUserLoansInfo(
    indexerClient: IndexerClient,
    loanAppId: int,
    poolManagerAppId: int,
    oracle: Oracle,
    userAddr: str,
    additionalInterests: AssetsAdditionalInterest | None = None,
) -> list[UserLoanInfo]:
    """
    Returns information regarding the loan escrows of a given user.

    @param indexerClient - Algorand indexer client to query
    @param loanAppId - loan application to query about
    @param poolManagerAppId - pool manager application to query about
    @param oracle - oracle to query
    @param userAddr - account address for the user
    @param additionalInterests - optional additional interest to consider in loan net rate/yield
    @returns Promise<UserLoanInfo[]> user loans infos
    """
    userLoanInfos: list[UserLoanInfo] = []

    # get all prerequisites
    escrows = getEscrows(indexerClient, userAddr, loanAppId, "la ", "lr ")
    loanInfo = retrieveLoanInfo(indexerClient, loanAppId)
    poolManagerInfo = retrievePoolManagerInfo(indexerClient, poolManagerAppId)
    oraclePrices = getOraclePrices(indexerClient, oracle)

    # get all remaining loans' info
    for escrowAddr in escrows:
        state = get_local_state_at_app(indexerClient, loanAppId, escrowAddr)
        if state is None:
            raise LookupError(f"Could not find loan {loanAppId} in escrow {escrowAddr}")
        localState = loanLocalState(state, loanAppId, escrowAddr)
        userLoanInfos.append(
            userLoanInfo(
                localState, poolManagerInfo, loanInfo, oraclePrices, additionalInterests
            )
        )

    return userLoanInfos


def retrieveUserLoanInfo(
    client: IndexerClient,
    loanAppId: int,
    poolManagerAppId: int,
    oracle: Oracle,
    escrowAddr: str,
    additionalInterests: AssetsAdditionalInterest | None = None,
) -> UserLoanInfo:
    """
    Returns information regarding the given user loan escrow.

    @param client - Algorand client to query
    @param loanAppId - loan application to query about
    @param poolManagerAppId - pool manager application to query about
    @param oracle - oracle to query
    @param escrowAddr - account address for the loan escrow
    @param additionalInterests - optional additional interest to consider in loan net rate/yield
    @returns Promise<UserLoanInfo> user loan info
    """
    # get all prerequisites
    poolManagerInfo = retrievePoolManagerInfo(client, poolManagerAppId)
    loanInfo = retrieveLoanInfo(client, loanAppId)
    oraclePrices = getOraclePrices(client, oracle)

    # get loan info
    state = get_local_state_at_app(client, loanAppId, escrowAddr)
    if state is None:
        raise LookupError(f"Could not find loan {loanAppId} in escrow {escrowAddr}")
    localState = loanLocalState(state, loanAppId, escrowAddr)
    return userLoanInfo(
        localState, poolManagerInfo, loanInfo, oraclePrices, additionalInterests
    )


def retrieveLiquidatableLoans(
    indexer: IndexerClient,
    loanAppId: int,
    poolManagerInfo: PoolManagerInfo,
    loanInfo: LoanInfo,
    oraclePrices: OraclePrices,
) -> list[UserLoanInfo]:
    """
    Returns all loans that are liquidatable.

    @param indexerClient - Algorand indexer client to query
    @param loanAppId - loan application to query about
    @param poolManagerInfo - pool manager info which is returned by retrievePoolManagerInfo function
    @param loanInfo - loan info which is returned by retrieveLoanInfo function
    @param oraclePrices - oracle prices which is returned by getOraclePrices function
    @param nextToken - token for retrieving next escrows
    @returns Promise<{ loans: UserLoanInfo[], nextToken?: string}> object containing liquidatable loans and next token
    """
    loans: list[UserLoanInfo] = []

    next_page = ""
    escrows = []
    while next_page is not None:
        res = indexer.accounts(
            limit=1000,
            next_page=next_page,
            application_id=loanAppId,
            exclude="assets,created-assets,created-apps",
        )
        # filter loans
        for account in res["accounts"]:
            escrowAddr = account["address"]
            user_local_state = account.get("apps-local-state", [])
            for app_local_state in user_local_state:
                if app_local_state["id"] == loanAppId:
                    state = format_state(app_local_state.get("key-value", []))
                    localState = loanLocalState(state, loanAppId, escrowAddr)
                    loan = userLoanInfo(
                        localState, poolManagerInfo, loanInfo, oraclePrices
                    )

                    if (
                        loan.totalEffectiveCollateralBalanceValue
                        < loan.totalEffectiveBorrowBalanceValue
                    ):
                        loans.append(loan)
                        escrows.append(escrowAddr)

        if "next-token" in res:
            next_page = res["next-token"]
        else:
            next_page = None

    return loans


def getMaxReduceCollateralForBorrowUtilisationRatio(
    loan: UserLoanInfo,
    colPoolAppId: int,
    targetBorrowUtilisationRatio: int,
) -> int:
    """
    Returns the maximum reduce collateral of a given f asset considering a target borrow utilisation ratio.
    Returns 0 if no collateral in loan.
    Returns at most the collateral balance.

    @param loan - user loan
    @param colPoolAppId - price of asset borrowing 14 d.p.
    @param targetBorrowUtilisationRatio - the utilisation ratio that you are targeting 4 d.p.
    @returns bigint max f asset amount
    """
    collateral = next(
        (c for c in loan.collaterals if c.poolAppId == colPoolAppId), None
    )

    # if could not find collateral or target is below actual, return 0
    if (
        collateral is None
        or targetBorrowUtilisationRatio <= loan.borrowUtilisationRatio
    ):
        return 0

    # check if can reduce all collateral (special case as lack required precision otherwise)
    newEffectiveBalanceValue = (
        loan.totalEffectiveCollateralBalanceValue - collateral.effectiveBalanceValue
    )
    newBorrowUtilisationRatio = calcBorrowUtilisationRatio(
        loan.totalEffectiveBorrowBalanceValue,
        newEffectiveBalanceValue,
    )
    if not (
        newEffectiveBalanceValue == 0 and loan.totalEffectiveBorrowBalanceValue > 0
    ) and (newBorrowUtilisationRatio <= targetBorrowUtilisationRatio):
        return collateral.fAssetBalance

    # calculate max
    targetEffectiveCollateralBalanceValue = divScale(
        loan.totalEffectiveBorrowBalanceValue,
        targetBorrowUtilisationRatio,
        ONE_4_DP,
    )  # 4 d.p.
    deltaEffectiveBalanceValue = (
        loan.totalEffectiveCollateralBalanceValue
        - targetEffectiveCollateralBalanceValue
    )  # 4 d.p.
    deltaBalanceValue = divScale(
        deltaEffectiveBalanceValue, collateral.collateralFactor, ONE_4_DP
    )  # 4 d.p.
    deltaAssetBalance = divScale(
        deltaBalanceValue, collateral.assetPrice, ONE_10_DP
    )  # 0 d.p.
    deltafAssetBalance = calcDepositReturn(
        deltaAssetBalance, collateral.depositInterestIndex
    )
    return min(deltafAssetBalance, collateral.fAssetBalance)


def getMaxBorrowForBorrowUtilisationRatio(
    loan: UserLoanInfo,
    assetPrice: int,
    borrowFactor: int,
    targetBorrowUtilisationRatio: int,
) -> int:
    """
    Returns the maximum borrow of a given asset considering a target borrow utilisation ratio.
    Returns 0 if cannot borrow anything more.

    @param loan - user loan
    @param assetPrice - price of asset borrowing 14 d.p.
    @param borrowFactor - borrow factor of asset borrowing 4 d.p.
    @param targetBorrowUtilisationRatio - the utilisation ratio that you are targeting 4 d.p.
    @returns bigint max asset amount
    """
    # if target is below actual, return 0
    if targetBorrowUtilisationRatio <= loan.borrowUtilisationRatio:
        return 0

    # calculate max
    targetEffectiveBorrowBalanceValue = mulScale(
        loan.totalEffectiveCollateralBalanceValue,
        targetBorrowUtilisationRatio,
        ONE_4_DP,
    )  # 4 d.p.
    deltaEffectiveBalanceValue = (
        targetEffectiveBorrowBalanceValue - loan.totalEffectiveBorrowBalanceValue
    )  # 4 d.p.
    deltaBalanceValue = divScale(
        deltaEffectiveBalanceValue, borrowFactor, ONE_4_DP
    )  # 4 d.p.
    deltaAssetBalance = divScale(deltaBalanceValue, assetPrice, ONE_10_DP)  # 0 d.p.
    return deltaAssetBalance


def getUserLoanAssets(pools: dict[str, Pool], loan: UserLoanInfo) -> tuple[list, list]:
    """
    Returns assets used in the loan: LP-assets and base assets
    """
    lpAssets: list[LPToken] = []
    baseAssetIds: list[int] = []
    # use set to remove duplicates (assets which are both collateral and borrow)
    loanPoolAppIds = set()

    def getAssetFromAppId(pools: dict[str, Pool], appId: int):
        pool = next(p for p in pools.values() if p.appId == appId)
        if pool:
            return pool.assetId
        else:
            raise LookupError(f"Cannot find asset for pool app id {appId}")

    for collateral_info in loan.collaterals:
        loanPoolAppIds.add(collateral_info.poolAppId)

    for borrow_info in loan.borrows:
        loanPoolAppIds.add(borrow_info.poolAppId)

    # add to lp assets and base assets
    for poolAppId in loanPoolAppIds:
        asset = getAssetFromAppId(pools, poolAppId)
        if isinstance(asset, int):
            baseAssetIds.append(asset)
        else:
            lpAssets.append(asset)

    return (lpAssets, baseAssetIds)


def prepareCreateUserLoan(
    loanAppId: int,
    userAddr: str,
    params: SuggestedParams,
) -> tuple[list[Transaction], Account]:
    """
    Returns a group transaction to create loan escrow.

    @param loanAppId - loan application to add escrow for
    @param userAddr - account address for the user
    @param params - suggested params for the transactions with the fees overwritten
    @returns { txns: Transaction[], escrow: Account } object containing group transaction and generated escrow account
    """
    key, address = generate_account()
    escrow = Account(addr=address, sk=key)

    userCall = addEscrowNoteTransaction(
        userAddr, escrow.addr, loanAppId, "la ", sp_fee(params, fee=2000)
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=escrow.addr,
        signer=signer,
        app_id=loanAppId,
        on_complete=OnComplete.OptInOC,
        method=loanABIContract.get_method_by_name("create_loan"),
        method_args=[TransactionWithSigner(userCall, signer)],
        rekey_to=get_application_address(loanAppId),
        sp=sp_fee(params, fee=0),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns, escrow


def prepareAddCollateralToLoan(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to add a collateral to a loan escrow.

    @param loanAppId - loan application to add collateral in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param pool - pool to add f asset of
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction add collateral to loan escrow transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId
    poolManagerIndex = pool.poolManagerIndex
    poolLoans = pool.loans

    poolLoanIndex = poolLoans.get(loanAppId, None)
    if poolLoanIndex is None:
        raise ValueError("Pool is not in loan")

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("add_collateral"),
        method_args=[
            escrowAddr,
            fAssetId,
            poolAppId,
            poolManagerIndex,
            poolLoanIndex,
            poolManagerAppId,
        ],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareSyncCollateralInLoan(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    oracle: Oracle,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a transaction to sync collateral of a loan escrow.

    @param loanAppId - loan application to sync collateral in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param pool - pool to sync collateral of
    @param oracle - oracle application to retrieve asset price from
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] sync collateral group transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId
    oracleAdapterAppId = oracle.oracleAdapterAppId

    # refresh prices
    lpAssets = [pool.lpToken] if hasattr(pool, "lpToken") else []
    baseAssetIds = [] if hasattr(pool, "lpToken") else [pool.assetId]
    refreshPrices = prepareRefreshPricesInOracleAdapter(
        oracle, userAddr, lpAssets, baseAssetIds, params
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("sync_collateral"),
        method_args=[
            TransactionWithSigner(refreshPrices[-1], signer),
            escrowAddr,
            fAssetId,
            poolAppId,
            poolManagerAppId,
            oracleAdapterAppId,
        ],
        sp=sp_fee(params, fee=1000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return refreshPrices[:-1] + txns


def prepareReduceCollateralFromLoan(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    pool: Pool,
    oracle: Oracle,
    lpAssets: list[LPToken],
    baseAssetIds: list[int],
    amount: int,
    isfAssetAmount: bool,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a transaction to reduce collateral of a loan escrow.

    @param loanAppId - loan application to reduce collateral in
    @param poolManagerAppId - pool manager application*
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param receiverAddr - account address to receive the collateral (typically the user's deposit escrow)
    @param pool - pool to reduce collateral of
    @param oracle - oracle application to retrieve asset prices from
    @param lpAssets - list of lp assets in loan
    @param baseAssetIds - list of base asset ids in loan (non-lp assets)
    @param amount - the amount of asset / f asset to reduce the collateral by
    @param isfAssetAmount - whether the amount of collateral to reduce by is expressed in terms of f asset or asset
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] reduce collateral group transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId
    oracleAdapterAppId = oracle.oracleAdapterAppId

    refreshPrices = prepareRefreshPricesInOracleAdapter(
        oracle, userAddr, lpAssets, baseAssetIds, params
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("reduce_collateral"),
        method_args=[
            TransactionWithSigner(refreshPrices[-1], signer),
            escrowAddr,
            receiverAddr,
            assetId,
            fAssetId,
            amount,
            isfAssetAmount,
            poolAppId,
            poolManagerAppId,
            oracleAdapterAppId,
        ],
        sp=sp_fee(params, fee=6000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return refreshPrices[:-1] + txns


def prepareSwapCollateralInLoanBegin(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    pool: Pool,
    amount: int,
    isfAssetAmount: bool,
    txnIndexForSwapCollateralEnd: int,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to begin swap collateral in a loan escrow.
    Must be groped together with swap_collateral_end call.

    @param loanAppId - loan application to swap collateral in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param receiverAddr - account address to receive the collateral (typically the user's deposit escrow)
    @param pool - pool to swap collateral of
    @param amount - the amount of asset / f asset to reduce the collateral by
    @param isfAssetAmount - whether the amount of collateral to reduce by is expressed in terms of f asset or asset
    @param txnIndexForSwapCollateralEnd - transaction index in the group transaction for the swap_collateral_end call.
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction swap collateral begin transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("swap_collateral_begin"),
        method_args=[
            escrowAddr,
            receiverAddr,
            assetId,
            fAssetId,
            amount,
            isfAssetAmount,
            txnIndexForSwapCollateralEnd,
            poolAppId,
            poolManagerAppId,
        ],
        sp=sp_fee(params, fee=6000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareSwapCollateralInLoanEnd(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    oracle: Oracle,
    lpAssets: list[LPToken],
    baseAssetIds: list[int],
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to end swap collateral in a loan escrow.
    Must be groped together with swap_collateral_begin call.

    @param loanAppId - loan application to swap collateral in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param oracle - oracle application to retrieve asset prices from
    @param lpAssets - list of lp assets in loan
    @param baseAssetIds - list of base asset ids in loan (non-lp assets)
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] swap collateral end group transaction
    """
    oracleAdapterAppId = oracle.oracleAdapterAppId

    refreshPrices = prepareRefreshPricesInOracleAdapter(
        oracle, userAddr, lpAssets, baseAssetIds, params
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("swap_collateral_end"),
        method_args=[
            TransactionWithSigner(refreshPrices[-1], signer),
            escrowAddr,
            poolManagerAppId,
            oracleAdapterAppId,
        ],
        sp=sp_fee(params, fee=1000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return refreshPrices[:-1] + txns


def prepareRemoveCollateralFromLoan(
    loanAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to remove collateral from loan escrow.

    @param loanAppId - loan application to remove collateral in
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param pool - pool to remove collateral of
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction remove collateral transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("remove_collateral"),
        method_args=[escrowAddr, fAssetId, poolAppId],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareBorrowFromLoan(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    pool: Pool,
    oracle: Oracle,
    lpAssets: list[LPToken],
    baseAssetIds: list[int],
    borrowAmount: int,
    maxStableRate: int,  # if zero then variable borrow
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to borrow using loan escrow.

    @param loanAppId - loan application to borrow in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param receiverAddr - account address to receive the borrow (typically the user)
    @param pool - pool to borrow from
    @param oracle - oracle application to retrieve asset prices from
    @param lpAssets - list of lp assets in loan
    @param baseAssetIds - list of base asset ids in loan (non-lp assets)
    @param borrowAmount - amount to borrow of asset
    @param maxStableRate - maximum stable rate of the borrow, if zero then borrow is interpreted as a variable rate borrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] borrow group transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    poolManagerIndex = pool.poolManagerIndex
    poolLoans = pool.loans
    oracleAdapterAppId = oracle.oracleAdapterAppId

    poolLoanIndex = poolLoans.get(loanAppId, None)
    if poolLoanIndex is None:
        raise ValueError("Pool is not in loan")

    refreshPrices = prepareRefreshPricesInOracleAdapter(
        oracle, userAddr, lpAssets, baseAssetIds, params
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("borrow"),
        method_args=[
            TransactionWithSigner(refreshPrices[-1], signer),
            escrowAddr,
            receiverAddr,
            assetId,
            borrowAmount,
            maxStableRate,
            poolManagerIndex,
            poolLoanIndex,
            poolAppId,
            poolManagerAppId,
            oracleAdapterAppId,
        ],
        sp=sp_fee(params, fee=8000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return refreshPrices[:-1] + txns


def prepareSwitchBorrowTypeInLoan(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    maxStableRate: int,  # ignored if not switching to stable borrow
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to switch borrow type of a loan borrow.

    @param loanAppId - loan application to switch borrow type in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param pool - pool to switch borrow type of
    @param maxStableRate - maximum stable rate of the borrow, if zero then interpreted as switching a stable rate borrow to a variable rate borrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] switch borrow type transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("switch_borrow_type"),
        method_args=[escrowAddr, assetId, maxStableRate, poolAppId, poolManagerAppId],
        sp=sp_fee(params, fee=6000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareRepayLoanWithTxn(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    reserveAddr: str,
    pool: Pool,
    repayAmount: int,
    isStable: bool,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to repay borrow in a loan escrow using assets sent from user.

    @param loanAppId - loan application to repay borrow in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param receiverAddr - account address to receive the rewards if any (typically the user's deposit escrow)
    @param reserveAddr - account address to receive the protocol revenue from the percentage of the accrued interest
    @param pool - pool to repay borrow of
    @param repayAmount - amount of borrow to repay
    @param isStable - whether the borrow that is being repaid is a stable or variable rate borrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] reduce borrow with transaction group transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    frAssetId = pool.frAssetId

    sendAsset = transferAlgoOrAsset(
        assetId,
        userAddr,
        get_application_address(poolAppId),
        repayAmount,
        sp_fee(params, fee=0),
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("repay_with_txn"),
        method_args=[
            TransactionWithSigner(sendAsset, signer),
            escrowAddr,
            receiverAddr,
            reserveAddr,
            assetId,
            frAssetId,
            isStable,
            poolAppId,
            poolManagerAppId,
        ],
        sp=sp_fee(params, fee=10000),
    )
    return remove_signer_and_group(atc.build_group())


def prepareRepayLoanWithCollateral(
    loanAppId: int,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    reserveAddr: str,
    pool: Pool,
    repayAmount: int,
    isStable: bool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a group transaction to repay borrow in a loan escrow using collateral.

    @param loanAppId - loan application to repay borrow in
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param receiverAddr - account address to receive the rewards if any (typically the user's deposit escrow)
    @param reserveAddr - account address to receive the protocol revenue from the percentage of the accrued interest
    @param pool - pool to repay borrow and use collateral of
    @param repayAmount - amount of borrow to repay expressed in terms of the asset
    @param isStable - whether the borrow that is being repaid is a stable or variable rate borrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] repay borrow with collateral group transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId
    frAssetId = pool.frAssetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("repay_with_collateral"),
        method_args=[
            escrowAddr,
            receiverAddr,
            reserveAddr,
            assetId,
            fAssetId,
            frAssetId,
            repayAmount,
            isStable,
            poolAppId,
            poolManagerAppId,
        ],
        sp=sp_fee(params, fee=14000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareLiquidateLoan(
    loanAppId: int,
    poolManagerAppId: int,
    liquidatorAddr: str,
    escrowAddr: str,
    reserveAddr: str,
    collateralPool: Pool,
    borrowPool: Pool,
    oracle: Oracle,
    lpAssets: list[LPToken],
    baseAssetIds: list[int],
    repayAmount: int,
    minCollateralAmount: int,
    isStable: bool,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to repay borrow in a loan escrow using assets sent from user.

    @param loanAppId - loan application to repay borrow in
    @param poolManagerAppId - pool manager application
    @param liquidatorAddr - account address for the liquidator
    @param escrowAddr - account address for the loan escrow
    @param reserveAddr - account address to receive the protocol revenue from the percentage of the accrued interest
    @param collateralPool - pool to seize collateral of
    @param borrowPool - pool to repay borrow of
    @param oracle - oracle application to retrieve asset prices from
    @param lpAssets - list of lp assets in loan
    @param baseAssetIds - list of base asset ids in loan (non-lp assets)
    @param repayAmount - amount of borrow to repay expressed in terms of borrow pool asset
    @param minCollateralAmount - minimum collateral amount for the liquidator to receive expressed in terms of collateral pool f asset
    @param isStable - whether the borrow that is being repaid is a stable or variable rate borrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] liquidate group transaction
    """
    colPoolAppId = collateralPool.appId
    fAssetId = collateralPool.fAssetId
    borPoolAppId = borrowPool.appId
    assetId = borrowPool.assetId
    oracleAdapterAppId = oracle.oracleAdapterAppId

    refreshPrices = prepareRefreshPricesInOracleAdapter(
        oracle, liquidatorAddr, lpAssets, baseAssetIds, params
    )

    sendAsset = transferAlgoOrAsset(
        assetId,
        liquidatorAddr,
        get_application_address(borPoolAppId),
        repayAmount,
        sp_fee(params, fee=0),
    )

    atc = AtomicTransactionComposer()

    atc.add_method_call(
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("liquidate"),
        sender=liquidatorAddr,
        sp=sp_fee(params, fee=10000),
        signer=signer,
        method_args=[
            TransactionWithSigner(refreshPrices[-1], signer),
            TransactionWithSigner(sendAsset, signer),
            escrowAddr,
            reserveAddr,
            assetId,
            fAssetId,
            minCollateralAmount,
            isStable,
            colPoolAppId,
            borPoolAppId,
            poolManagerAppId,
            oracleAdapterAppId,
        ],
    )

    return remove_signer_and_group(atc.build_group())


def prepareRebalanceUpLoan(
    loanAppId: int,
    poolManagerAppId: int,
    rebalancerAddr: str,
    escrowAddr: str,
    pool: Pool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to rebalance up borrow in a loan escrow.

    @param loanAppId - loan application to rebalance up borrow in
    @param poolManagerAppId - pool manager application*
    @param rebalancerAddr - account address for the rebalancer
    @param escrowAddr - account address for the loan escrow
    @param pool - pool to rebalance
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction rebalance up transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=rebalancerAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("rebalance_up"),
        method_args=[escrowAddr, assetId, poolAppId, poolManagerAppId],
        sp=sp_fee(params, fee=5000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareRebalanceDownLoan(
    loanAppId: int,
    poolManagerAppId: int,
    rebalancerAddr: str,
    escrowAddr: str,
    pool: Pool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to rebalance up borrow in a loan escrow.

    @param loanAppId - loan application to rebalance down borrow in
    @param poolManagerAppId - pool manager application
    @param rebalancerAddr - account address for the rebalancer
    @param escrowAddr - account address for the loan escrow
    @param pool - pool to rebalance
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction rebalance down transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=rebalancerAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("rebalance_down"),
        method_args=[escrowAddr, assetId, poolAppId, poolManagerAppId],
        sp=sp_fee(params, fee=5000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareRemoveUserLoan(
    loanAppId: int,
    userAddr: str,
    escrowAddr: str,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to remove a user's loan escrow and return its minimum balance to the user.

    @param loanAppId - loan application to remove loan in
    @param userAddr - account address for the user
    @param escrowAddr - account address for the loan escrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] remove and close out loan escrow group transaction
    """
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=loanAppId,
        method=loanABIContract.get_method_by_name("remove_loan"),
        method_args=[escrowAddr],
        sp=sp_fee(params, fee=4000),
    )
    txns = remove_signer_and_group(atc.build_group())
    optOutTx = ApplicationCloseOutTxn(escrowAddr, sp_fee(params, fee=0), loanAppId)
    closeToTx = removeEscrowNoteTransaction(
        escrowAddr, userAddr, "lr ", sp_fee(params, fee=0)
    )
    return [txns[0], optOutTx, closeToTx]


def prepareFlashLoanBegin(
    pool: Pool,
    userAddr: str,
    receiverAddr: str,
    borrowAmount: int,
    txnIndexForFlashLoanEnd: int,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to begin flash loan
    Must be groped together with flash_loan_end call.

    @param pool - pool to borrow from
    @param userAddr - account address for the user
    @param receiverAddr - account address to receive the loan
    @param borrowAmount - the amount of the asset to borrow
    @param txnIndexForFlashLoanEnd - transaction index in the group transaction for the flash_loan_end call.
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction flash loan begin transaction
    """
    appId = pool.appId
    assetId = pool.assetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=appId,
        method=poolABIContract.get_method_by_name("flash_loan_begin"),
        method_args=[borrowAmount, txnIndexForFlashLoanEnd, receiverAddr, assetId],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareFlashLoanEnd(
    pool: Pool,
    userAddr: str,
    reserveAddr: str,
    repaymentAmount: int,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to end flash loan.
    Must be groped together with flash_loan_begin call.

    @param pool - pool borrowed from
    @param userAddr - account address for the user
    @param reserveAddr - account address to receive the protocol revenue from the flash loan fee
    @param repaymentAmount - the amount of the asset to repay (borrow amount plus flash loan fee)
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] flash loan end group transaction
    """
    appId = pool.appId
    assetId = pool.assetId

    sendAsset = transferAlgoOrAsset(
        assetId,
        userAddr,
        get_application_address(appId),
        repaymentAmount,
        sp_fee(params, fee=0),
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=appId,
        method=poolABIContract.get_method_by_name("flash_loan_end"),
        method_args=[TransactionWithSigner(sendAsset, signer), reserveAddr, assetId],
        sp=sp_fee(params, fee=3000),
    )
    return remove_signer_and_group(atc.build_group())


def wrapWithFlashLoan(
    txns: list[Transaction],
    pool: Pool,
    userAddr: str,
    receiverAddr: str,
    reserveAddr: str,
    borrowAmount: int,
    params: SuggestedParams,
    flashLoanFee: int = int(0.001e16),
) -> list[Transaction]:
    """
    Wraps given transactions with flash loan.

    @param txns - txns to wrap flash loan around
    @param pool - pool to borrow from
    @param userAddr - account address for the user
    @param receiverAddr - account address to receive the loan
    @param reserveAddr - account address to receive the protocol revenue from the flash loan fee
    @param borrowAmount - the amount of the asset to borrow
    @param params - suggested params for the transactions with the fees overwritten
    @param flashLoanFee - fee for flash loan as 16 d.p integer (default 0.1%)
    @returns Transaction[] group transaction wrapped with flash loan
    """
    # clear group id in passed txns
    wrappedTxns = [t for t in txns]
    for txn in wrappedTxns:
        txn.group = None

    # add flash loan begin
    txnIndexForFlashLoanEnd = len(txns) + 2
    flashLoanBegin = prepareFlashLoanBegin(
        pool, userAddr, receiverAddr, borrowAmount, txnIndexForFlashLoanEnd, params
    )
    wrappedTxns = [flashLoanBegin] + wrappedTxns

    # add flash loan end
    repaymentAmount = calcFlashLoanRepayment(int(borrowAmount), flashLoanFee)
    flashLoanEnd = prepareFlashLoanEnd(
        pool, userAddr, reserveAddr, repaymentAmount, params
    )
    wrappedTxns.extend(flashLoanEnd)

    # return txns wrapped with flash loan
    return wrappedTxns
