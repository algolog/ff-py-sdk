from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass
class ReferrerTransaction:
    unsignedTxn: str  # msgpack encoded, base64 format
    lsig: Optional[str] = None


ReferrerGroupTransaction = list[ReferrerTransaction]


@dataclass
class Tier:
    amount: int
    discount: float  # 0 d.p. (20=20%)


@dataclass
class DiscountTiers:
    assetId: int
    tiers: list[Tier]


class SwapMode(Enum):
    FIXED_INPUT = "FIXED_INPUT"
    FIXED_OUTPUT = "FIXED_OUTPUT"


@dataclass
class SwapParams:
    fromAssetId: int
    toAssetId: int
    amount: int
    swapMode: SwapMode


@dataclass
class SwapQuote:
    quoteAmount: int
    priceImpact: float
    microalgoTxnsFee: int
    txnPayload: str


SwapTransactions = list[str]
