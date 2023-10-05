from dataclasses import dataclass


@dataclass
class XAlgo:
    appId: int
    xAlgoId: int


@dataclass
class XAlgoInfo:
    timeDelay: int
    commitEnd: int
    fee: int  # 4 d.p.
    hasClaimedFee: bool
    isMintingPaused: bool
    algoBalance: int
    xAlgoCirculatingBalance: int
