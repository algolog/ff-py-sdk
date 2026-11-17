# CONSTANTS

ALGO_ASSET_ID = 0

PAYOUTS_GO_ONLINE_FEE = 2_000_000

MIN_FEE = 1000  # per txn, including inner txns
PQ_FEE_PREMIUM = 2000  # extra for falcon-signed txns
USER_TXN_FEE = MIN_FEE + PQ_FEE_PREMIUM  # fee for each txn sent by the user

# ENUMS


class Network:
    """Enum specifying the network"""

    MAINNET = 0
    TESTNET = 1
