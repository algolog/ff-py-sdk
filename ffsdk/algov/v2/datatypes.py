from dataclasses import dataclass
from typing import Optional


@dataclass
class DistributorInfo:
    dispenserAppId: int  # id of dispenser app which mints gALGO
    premintEnd: int  # unix timestamp for the end of the pre-mint period
    commitEnd: int  # unix timestamp for end of the commitment period
    periodEnd: int  # unix timestamp for end of the governance period
    fee: int  # minting fee 4 d.p.
    totalCommitment: int  # total amount of ALGOs committed
    isBurningPaused: bool  # flag to indicate if users can burn their ALGO for gALGO


@dataclass
class UserCommitmentInfo:
    userAddress: str
    canDelegate: bool  # whether voting can be delegated to admin
    premint: int  # amount of ALGOs the user has pre-minted and not yet claimed
    commitment: int  # amount of ALGOs the user has committed
    nonCommitment: int  # amount of ALGOs the user has added after the commitment period


@dataclass
class EscrowGovernaceInfo:
    version: int
    commitment: int
    beneficiaryAddress: Optional[str] = None
    xGovControlAddress: Optional[str] = None


@dataclass
class EscrowGovernanceStatus:
    balance: int
    isOnline: bool
    status: Optional[EscrowGovernaceInfo] = None
