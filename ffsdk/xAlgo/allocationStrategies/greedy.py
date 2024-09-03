from ..datatypes import ProposerAllocations, ConsensusState
from ..formulae import convertAlgoToXAlgoWhenDelay
from .constants import FIXED_CAPACITY_BUFFER, MAX_APPL_CALLS


def greedyStakeAllocationStrategy(
    consensusState: ConsensusState,
    amount: int,
) -> ProposerAllocations:
    proposersBalances = consensusState.proposersBalances
    maxProposerBalance = consensusState.maxProposerBalance
    allocation = [0] * len(proposersBalances)

    # sort in ascending order
    indexed = [(p.algoBalance, idx) for idx, p in enumerate(proposersBalances)]
    indexed.sort()

    # allocate to proposers in greedy approach
    remaining = amount
    for i in range(min(len(allocation), MAX_APPL_CALLS)):
        proposerAlgoBalance, proposerIndex = indexed[i]

        # under-approximate capacity to leave wiggle room
        algoCapacity = max(
            maxProposerBalance - proposerAlgoBalance - FIXED_CAPACITY_BUFFER, 0
        )
        allocate = min(remaining, algoCapacity)
        allocation[proposerIndex] = allocate

        # exit if fully allocated
        remaining -= allocate
        if remaining <= 0:
            break

    # handle case where still remaining
    if remaining > 0:
        raise ValueError("Insufficient capacity to stake")

    return allocation


def greedyUnstakeAllocationStrategy(
    consensusState: ConsensusState,
    amount: int,
) -> ProposerAllocations:
    proposersBalances = consensusState.proposersBalances
    minProposerBalance = consensusState.minProposerBalance
    allocation = [0] * len(proposersBalances)

    # sort in descending order
    indexed = [(p.algoBalance, idx) for idx, p in enumerate(proposersBalances)]
    indexed.sort(reverse=True)

    # allocate to proposers in greedy approach
    remaining = amount
    for i in range(min(len(allocation), MAX_APPL_CALLS)):
        proposerAlgoBalance, proposerIndex = indexed[i]

        # under-approximate capacity to leave wiggle room
        algoCapacity = max(
            proposerAlgoBalance - minProposerBalance - FIXED_CAPACITY_BUFFER, 0
        )
        xAlgoCapacity = convertAlgoToXAlgoWhenDelay(algoCapacity, consensusState)
        allocate = min(remaining, xAlgoCapacity)
        allocation[proposerIndex] = allocate

        # exit if fully allocated
        remaining -= allocate
        if remaining <= 0:
            break

    # handle case where still remaining
    if remaining > 0:
        raise ValueError(
            "Insufficient capacity to unstake - override with your own allocation"
        )

    return allocation
