from dataclasses import dataclass


@dataclass
class ConsensusConfig:
    appId: int
    xAlgoId: int


@dataclass
class ProposerBalance:
    address: str
    algoBalance: int


@dataclass
class ConsensusState:
    currentRound: int  # round the data was read at
    algoBalance: int
    xAlgoCirculatingSupply: int
    proposersBalances: list[ProposerBalance]
    timeDelay: int
    numProposers: int
    minProposerBalance: int
    maxProposerBalance: int
    fee: int  # 4 d.p.
    premium: int  # 16 d.p.
    totalPendingStake: int
    totalActiveStake: int
    totalRewards: int
    totalUnclaimedFees: int
    canImmediateStake: bool
    canDelayStake: bool


ProposerAllocations = list[int]
