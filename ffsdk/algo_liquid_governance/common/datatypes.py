from dataclasses import dataclass


@dataclass
class Dispenser:
    appId: int
    gAlgoId: int


@dataclass
class DispenserInfo:
    distributorAppIds: list[int]  # list of valid distributor app ids
    isMintingPaused: bool  # flag indicating if users can mint gALGO


@dataclass
class Distributor:
    appId: int
