import math

SECONDS_IN_YEAR = 365 * 24 * 60 * 60
HOURS_IN_YEAR = 365 * 24

ONE_2_DP = int(1e2)
ONE_4_DP = int(1e4)
ONE_10_DP = int(1e10)
ONE_12_DP = int(1e12)
ONE_14_DP = int(1e14)
ONE_16_DP = int(1e16)

UINT64 = 2 << 63
UINT128 = 2 << 127


def mulScale(n1: int, n2: int, scale: int) -> int:
    return (n1 * n2) // scale


def mulScaleRoundUp(n1: int, n2: int, scale: int) -> int:
    return mulScale(n1, n2, scale) + 1


def divScale(n1: int, n2: int, scale: int) -> int:
    return (n1 * scale) // n2


def divScaleRoundUp(n1: int, n2: int, scale: int) -> int:
    return divScale(n1, n2, scale) + 1


def expBySquaring(x: int, n: int, scale: int) -> int:
    if n == 0:
        return scale

    y = scale
    while n > 1:
        if n % 2:
            y = mulScale(x, y, scale)
            n = (n - 1) // 2
        else:
            n = n // 2
        x = mulScale(x, x, scale)

    return mulScale(x, y, scale)


def compound(rate: int, scale: int, period: int) -> int:
    return expBySquaring(scale + rate // period, period, scale) - scale


def compoundEverySecond(rate: int, scale: int) -> int:
    return compound(rate, scale, SECONDS_IN_YEAR)


def compoundEveryHour(rate: int, scale: int) -> int:
    return compound(rate, scale, HOURS_IN_YEAR)


def sqrt(value: int) -> int:
    return math.isqrt(value)
