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
from base64 import b64decode
from time import time
from .utils import getEscrows, depositStakingLocalState
from .datatypes import (
    Pool,
    DepositStakingInfo,
    DSInfoProgram,
    DSInfoReward,
    UserDepositStakingLocalState,
    Account,
)
from ..transaction_utils import (
    signer,
    sp_fee,
    remove_signer_and_group,
    addEscrowNoteTransaction,
    removeEscrowNoteTransaction,
)
from .abi_contracts import depositStakingABIContract
from ..state_utils import get_global_state, get_balances, get_local_state_at_app


def retrieveDepositStakingInfo(
    indexerClient: IndexerClient, depositStakingAppId: int
) -> DepositStakingInfo:
    """
    Returns information regarding the given deposit staking application.

    @param client - Algorand client to query
    @param depositStakingAppId - deposit staking application to query about
    @returns Promise<DepositStakingInfo> pool info
    """
    state = get_global_state(indexerClient, depositStakingAppId)

    # initialise staking program
    stakingPrograms = []
    for i in range(6):
        stakeBase64Value = state.get(f"S{i:c}")
        stakeValue = b64decode(stakeBase64Value).hex()

        for j in range(5):
            basePos = j * 46
            rewards: list[DSInfoReward] = []
            stakingPrograms.append(
                DSInfoProgram(
                    poolAppId=int(stakeValue[basePos : basePos + 12], base=16),
                    totalStaked=int(stakeValue[basePos + 12 : basePos + 28], base=16),
                    minTotalStaked=int(
                        stakeValue[basePos + 28 : basePos + 44], base=16
                    ),
                    stakeIndex=i * 5 + j,
                    numRewards=int(stakeValue[basePos + 44 : basePos + 46], base=16),
                    rewards=rewards,
                )
            )

    # add rewards
    for i in range(23):
        rewardBase64Value = state.get(f"R{i:c}")
        rewardValue = b64decode(rewardBase64Value).hex()
        max_j = 3 if (i != 22) else 1
        for j in range(max_j + 1):
            basePos = j * 60
            stakeIndex = (i * 4 + j) // 3
            localRewardIndex = (i * 4 + j) % 3
            sp = stakingPrograms[stakeIndex]
            numRewards = sp.numRewards
            if localRewardIndex >= numRewards:
                continue

            ts = max(sp.totalStaked, sp.minTotalStaked)
            endTimestamp = int(rewardValue[basePos + 12 : basePos + 20], base=16)
            lu = int(rewardValue[basePos + 20 : basePos + 28], base=16)
            rewardRate = int(rewardValue[basePos + 28 : basePos + 44], base=16)
            rpt = int(rewardValue[basePos + 44 : basePos + 60], base=16)
            currTime = int(time())
            dt = (
                (currTime - lu)
                if currTime <= endTimestamp
                else (endTimestamp - lu if lu <= endTimestamp else 0)
            )
            rewardPerToken = int(rpt + ((rewardRate * dt) / ts))
            rewardAssetId = int(rewardValue[basePos : basePos + 12], base=16)

            sp.rewards.append(
                DSInfoReward(rewardAssetId, endTimestamp, rewardRate, rewardPerToken)
            )

    return DepositStakingInfo(stakingPrograms)


def retrieveUserDepositStakingsLocalState(
    indexerClient: IndexerClient,
    depositStakingAppId: int,
    userAddr: str,
) -> list[UserDepositStakingLocalState]:
    """
    Returns local state regarding the deposit staking escrows of a given user.
    Use for advanced use cases where optimising number of network request.

    @param indexerClient - Algorand indexer client to query
    @param depositStakingAppId - deposit staking application to query about
    @param userAddr - account address for the user
    @returns Promise<UserDepositStakingLocalState[]> deposit staking escrows' local state
    """
    depositStakingsLocalState: list[UserDepositStakingLocalState] = []

    escrows = getEscrows(indexerClient, userAddr, depositStakingAppId, "fa ", "fr ")

    # get all remaining deposit stakings' local state
    for escrowAddr in escrows:
        holdings = get_balances(indexerClient, escrowAddr)
        optedIntoAssets = set(holdings.keys())
        state = get_local_state_at_app(indexerClient, depositStakingAppId, escrowAddr)
        if state is None:
            raise ValueError(
                f"Could not find deposit staking {depositStakingAppId} in escrow {escrowAddr}"
            )

        user_staking_state = depositStakingLocalState(
            state, depositStakingAppId, escrowAddr
        )
        user_staking_state.optedIntoAssets = optedIntoAssets
        depositStakingsLocalState.append(user_staking_state)

    return depositStakingsLocalState


def retrieveUserDepositStakingLocalState(
    indexerClient: IndexerClient,
    depositStakingAppId: int,
    escrowAddr: str,
) -> UserDepositStakingLocalState:
    """
    Returns local state regarding the deposit staking escrows of a given user.
    Use for advanced use cases where optimising number of network request.

    @param indexerClient - Algorand indexer client to query
    @param depositStakingAppId - deposit staking application to query about
    @param escrowAddr - account address for the deposit staking escrow
    @returns Promise<UserDepositStakingLocalState> deposit staking escrows' local state
    """

    state = get_local_state_at_app(indexerClient, depositStakingAppId, escrowAddr)
    if state is None:
        raise ValueError(
            f"Could not find deposit staking {depositStakingAppId} in escrow {escrowAddr}"
        )
    user_staking_state = depositStakingLocalState(state, depositStakingAppId, escrowAddr)
    holdings = get_balances(indexerClient, escrowAddr)
    user_staking_state.optedIntoAssets = set(holdings.keys())

    return user_staking_state


def prepareAddDepositStakingEscrow(
    depositStakingAppId: int,
    userAddr: str,
    params: SuggestedParams,
) -> tuple[list[Transaction], Account]:
    """
    Returns a group transaction to add deposit staking escrow.

    @param depositStakingAppId - deposit staking application to query about
    @param userAddr - account address for the user
    @param params - suggested params for the transactions with the fees overwritten
    @returns { txns: Transaction[], escrow: Account } object containing group transaction and generated escrow account
    """
    key, address = generate_account()
    escrow = Account(addr=address, sk=key)

    userCall = addEscrowNoteTransaction(
        userAddr, escrow.addr, depositStakingAppId, "fa ", sp_fee(params, fee=2000)
    )

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=escrow.addr,
        signer=signer,
        app_id=depositStakingAppId,
        on_complete=OnComplete.OptInOC,
        method=depositStakingABIContract.get_method_by_name("add_f_staking_escrow"),
        method_args=[TransactionWithSigner(userCall, signer)],
        rekey_to=get_application_address(depositStakingAppId),
        sp=sp_fee(params, fee=0),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns, escrow


def prepareOptDepositStakingEscrowIntoAsset(
    depositStakingAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    stakeIndex: int,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to opt deposit staking escrow into asset so that it can hold a given pool's f asset.

    @param depositStakingAppId - deposit staking application of escrow
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit staking escrow
    @param pool - pool to add f asset of
    @param stakeIndex - staking program index
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction opt deposit staking escrow into asset transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositStakingAppId,
        method=depositStakingABIContract.get_method_by_name("opt_escrow_into_asset"),
        method_args=[escrowAddr, poolAppId, fAssetId, stakeIndex],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareSyncStakeInDepositStakingEscrow(
    depositStakingAppId: int,
    pool: Pool,
    userAddr: str,
    escrowAddr: str,
    stakeIndex: int,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to sync stake of deposit staking escrow

    @param depositStakingAppId - deposit staking application of escrow
    @param pool - pool to sync stake of
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit staking escrow
    @param stakeIndex - staking program index
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction sync stake of deposit staking escrow transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId

    atc = AtomicTransactionComposer()

    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositStakingAppId,
        method=depositStakingABIContract.get_method_by_name("sync_stake"),
        method_args=[escrowAddr, poolAppId, fAssetId, stakeIndex],
        sp=sp_fee(params, fee=2000),
    )

    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareClaimRewardsOfDepositStakingEscrow(
    depositStakingAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    stakeIndex: int,
    rewardAssetIds: list[int],
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to claim the rewards of a deposit staking escrow

    @param depositStakingAppId - deposit staking application of escrow
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit staking escrow
    @param receiverAddr - account address to receive the withdrawal (typically the same as the user address)
    @param stakeIndex - staking program index
    @param rewardAssetIds - the asset ids of all the rewards assets claiming
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction withdraw from deposit staking escrow transaction
    """
    atc = AtomicTransactionComposer()

    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositStakingAppId,
        method=depositStakingABIContract.get_method_by_name("claim_rewards"),
        method_args=[escrowAddr, receiverAddr, stakeIndex],
        sp=sp_fee(params, fee=4000),
    )
    txns = remove_signer_and_group(atc.build_group())
    txns[0].foreign_assets = rewardAssetIds
    return txns[0]


def prepareWithdrawFromDepositStakingEscrow(
    depositStakingAppId: int,
    pool: Pool,
    poolManagerAppId: int,
    userAddr: str,
    escrowAddr: str,
    receiverAddr: str,
    amount: int,
    isfAssetAmount: bool,
    remainDeposited: bool,
    stakeIndex: int,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to withdraw from a deposit staking escrow

    @param depositStakingAppId - deposit staking application of escrow
    @param pool - pool to withdraw from
    @param poolManagerAppId - pool manager application
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit staking escrow
    @param receiverAddr - account address to receive the withdrawal (typically the same as the user address)
    @param amount - the amount of asset / f asset to send to withdraw from escrow.
    @param isfAssetAmount - whether the amount to withdraw is expressed in terms of f asset or asset
    @param remainDeposited - whether receiver should get f asset or asset (cannot remain deposited and use asset amount)
    @param stakeIndex - staking program index
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction withdraw from deposit staking escrow transaction
    """
    poolAppId = pool.appId
    assetId = pool.assetId
    fAssetId = pool.fAssetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositStakingAppId,
        method=depositStakingABIContract.get_method_by_name("withdraw_stake"),
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
            stakeIndex,
        ],
        sp=sp_fee(params, fee=6000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareOptOutDepositStakingEscrowFromAsset(
    depositStakingAppId: int,
    userAddr: str,
    escrowAddr: str,
    pool: Pool,
    params: SuggestedParams,
) -> Transaction:
    """
    Returns a transaction to remove asset from deposit staking escrow

    @param depositStakingAppId - deposit staking application of escrow
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit staking escrow
    @param pool - pool to remove f asset of
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction opt out deposit staking escrow from asset transaction
    """
    poolAppId = pool.appId
    fAssetId = pool.fAssetId

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositStakingAppId,
        method=depositStakingABIContract.get_method_by_name(
            "close_out_escrow_from_asset"
        ),
        method_args=[escrowAddr, get_application_address(poolAppId), fAssetId],
        sp=sp_fee(params, fee=3000),
    )
    txns = remove_signer_and_group(atc.build_group())
    return txns[0]


def prepareRemoveDepositStakingEscrow(
    depositStakingAppId: int,
    userAddr: str,
    escrowAddr: str,
    params: SuggestedParams,
) -> list[Transaction]:
    """
    Returns a group transaction to remove a user's deposit staking escrow and return its minimum balance to the user.

    @param depositStakingAppId - deposit staking application of escrow
    @param userAddr - account address for the user
    @param escrowAddr - account address for the deposit staking escrow
    @param params - suggested params for the transactions with the fees overwritten
    @returns Transaction[] remove and close out deposit staking escrow group transaction
    """
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=userAddr,
        signer=signer,
        app_id=depositStakingAppId,
        method=depositStakingABIContract.get_method_by_name("remove_f_staking_escrow"),
        method_args=[escrowAddr],
        sp=sp_fee(params, fee=2000),
    )
    txns = remove_signer_and_group(atc.build_group())
    optOutTx = ApplicationCloseOutTxn(escrowAddr, params, depositStakingAppId)
    closeToTx = removeEscrowNoteTransaction(escrowAddr, userAddr, "fr ", params)
    return [txns[0], optOutTx, closeToTx]
