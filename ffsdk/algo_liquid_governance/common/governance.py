from algosdk.v2client.indexer import IndexerClient
from .datatypes import Dispenser, DispenserInfo
from ...state_utils import get_global_state, parse_uint64s


def getDispenserInfo(
    indexerClient: IndexerClient, dispenser: Dispenser
) -> DispenserInfo:
    """
    Returns information regarding the given liquid governance dispenser.

    @param indexerClient - Algorand indexer client to query
    @param dispenser - dispenser to query about
    @returns DispenserInfo[] dispenser info
    """
    appId = dispenser.appId
    state = get_global_state(indexerClient, appId)

    distributorAppIds = parse_uint64s(state["distribs"])
    isMintingPaused = bool(state.get("is_minting_paused", 0))

    return DispenserInfo(
        distributorAppIds,
        isMintingPaused,
    )
