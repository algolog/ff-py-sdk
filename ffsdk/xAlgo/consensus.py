from base64 import b64encode, b64decode
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest
from algosdk.logic import get_application_address
from algosdk.encoding import encode_address
from algosdk.transaction import SuggestedParams, Transaction
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    EmptySigner,
)
from ..state_utils import get_global_state, get_application_box, parse_uint64s
from .constants.mainnet_constants import MAINNET_RESERVE_ADDRESS
from .abiContracts import xAlgoABIContract
from .datatypes import ConsensusConfig, ConsensusState, ProposerBalance


def getConsensusState(
    algodClient: AlgodClient, consensusConfig: ConsensusConfig
) -> ConsensusState:
    """
    Returns information regarding the given consensus application.

    @param algodClient - Algorand client to query
    @param consensusConfig - consensus application and xALGO config
    @returns ConsensusState current state of the consensus application
    """

    state = get_global_state(algodClient, consensusConfig.appId)
    box = get_application_box(algodClient, consensusConfig.appId, "pr".encode())
    current_round = box["round"]
    boxValue = b64decode(box["value"])
    params = algodClient.suggested_params()
    if not state:
        raise ValueError("Could not find xAlgo application")

    # xALGO rate
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        sender=MAINNET_RESERVE_ADDRESS,
        signer=EmptySigner(),
        app_id=consensusConfig.appId,
        method=xAlgoABIContract.get_method_by_name("get_xalgo_rate"),
        method_args=[],
        sp=params,
    )
    simReq = SimulateRequest(
        txn_groups=[],
        allow_empty_signatures=True,
        allow_unnamed_resources=True,
        extra_opcode_budget=70000,
    )
    methodResults = atc.simulate(algodClient, simReq).abi_results
    returnValue = methodResults[0].return_value
    algoBalance, xAlgoCirculatingSupply, balances = returnValue

    # proposers
    proposersBalances = [
        ProposerBalance(encode_address(boxValue[i * 32 : (i + 1) * 32]), balance)
        for i, balance in enumerate(parse_uint64s(b64encode(bytes(balances))))
    ]

    # global state
    timeDelay = int(state.get("time_delay", 0))
    numProposers = int(state.get("num_proposers", 0))
    minProposerBalance = int(state.get("min_proposer_balance", 0))
    maxProposerBalance = int(state.get("max_proposer_balance", 0))
    fee = int(state.get("fee", 0))
    premium = int(state.get("premium", 0))
    totalPendingStake = int(state.get("total_pending_stake", 0))
    totalActiveStake = int(state.get("total_active_stake", 0))
    totalRewards = int(state.get("total_rewards", 0))
    totalUnclaimedFees = int(state.get("total_unclaimed_fees", 0))
    canImmediateStake = bool(state.get("can_immediate_mint"))
    canDelayStake = bool(state.get("can_delay_mint"))

    return ConsensusState(
        current_round,
        algoBalance,
        xAlgoCirculatingSupply,
        proposersBalances,
        timeDelay,
        numProposers,
        minProposerBalance,
        maxProposerBalance,
        fee,
        premium,
        totalPendingStake,
        totalActiveStake,
        totalRewards,
        totalUnclaimedFees,
        canImmediateStake,
        canDelayStake,
    )
