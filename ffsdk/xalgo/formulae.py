from ..mathlib import mulScale, ONE_16_DP
from .datatypes import ConsensusState


def convertAlgoToXAlgoWhenImmediate(
    algoAmount: int, consensusState: ConsensusState
) -> int:
    algoBalance = consensusState.algoBalance
    xAlgoCirculatingSupply = consensusState.xAlgoCirculatingSupply
    premium = consensusState.premium
    return mulScale(
        mulScale(algoAmount, xAlgoCirculatingSupply, algoBalance),
        ONE_16_DP - premium,
        ONE_16_DP,
    )


def convertAlgoToXAlgoWhenDelay(algoAmount: int, consensusState: ConsensusState) -> int:
    algoBalance = consensusState.algoBalance
    xAlgoCirculatingSupply = consensusState.xAlgoCirculatingSupply
    return mulScale(algoAmount, xAlgoCirculatingSupply, algoBalance)


def convertXAlgoToAlgo(xAlgoAmount: int, consensusState: ConsensusState) -> int:
    algoBalance = consensusState.algoBalance
    xAlgoCirculatingSupply = consensusState.xAlgoCirculatingSupply
    return mulScale(xAlgoAmount, algoBalance, xAlgoCirculatingSupply)
