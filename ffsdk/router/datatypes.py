from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass
class ReferrerTransaction:
    unsignedTxn: bytes
    lsig: Optional[bytes] = None


ReferrerGroupTransaction = list[ReferrerTransaction]


class SwapMode(Enum):
    FIXED_INPUT = "FIXED_INPUT"
    FIXED_OUTPUT = "FIXED_OUTPUT"


@dataclass
class SwapQuote:
    quoteAmount: int
    priceImpact: float
    microalgoTxnsFee: int
    txnPayload: str


SwapTransactions = list[str]
