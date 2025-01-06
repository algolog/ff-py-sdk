from ..datatypes import LoanType

TESTNET_POOL_MANAGER_APP_ID = 147157634

TESTNET_DEPOSITS_APP_ID = 147157692

# type TestnetPoolKey = "ALGO" | "gALGO" | "xALGO" | "USDC" | "USDt" | "goBTC" | "goETH";
TestnetPools = {
  'ALGO': {
    'appId': 147169673,
    'assetId': 0,
    'fAssetId': 147171698,
    'frAssetId': 147171699,
    'assetDecimals': 6,
    'poolManagerIndex': 0,
    'loans': {
      147173131: int(0),
      168153622: int(0),
      397181473: int(1),
      397181998: int(1),
    },
  },
  'gALGO': {
    'appId': 168152517,
    'assetId': 167184545,
    'fAssetId': 168153084,
    'frAssetId': 168153085,
    'assetDecimals': 6,
    'poolManagerIndex': 5,
    'loans': {
      147173131: int(5),
      168153622: int(1),
    },
  },
  'xALGO': {
    'appId': 730786369,
    'assetId': 730430700,
    'fAssetId': 730786397,
    'frAssetId': 730786398,
    'assetDecimals': 6,
    'poolManagerIndex': 6,
    'loans': {
      147173131: int(6),
      168153622: int(2),
    },
  },
  'USDC': {
    'appId': 147170678,
    'assetId': 67395862,
    'fAssetId': 147171826,
    'frAssetId': 147171827,
    'assetDecimals': 6,
    'poolManagerIndex': 1,
    'loans': {
      147173131: int(1),
      147173190: int(0),
      397181473: int(0),
      397181998: int(0),
    },
  },
  'USDt': {
    'appId': 147171033,
    'assetId': 67396430,
    'fAssetId': 147172417,
    'frAssetId': 147172418,
    'assetDecimals': 6,
    'poolManagerIndex': 2,
    'loans': {
      147173131: int(2),
      147173190: int(1),
    },
  },
  'goBTC': {
    'appId': 147171314,
    'assetId': 67396528,
    'fAssetId': 147172646,
    'frAssetId': 147172647,
    'assetDecimals': 8,
    'poolManagerIndex': 3,
    'loans': {
      147173131: int(3),
      397181473: int(2),
      397181998: int(2),
    },
  },
  'goETH': {
    'appId': 147171345,
    'assetId': 76598897,
    'fAssetId': 147172881,
    'frAssetId': 147172882,
    'assetDecimals': 8,
    'poolManagerIndex': 4,
    'loans': {
      147173131: int(4),
      397181473: int(3),
      397181998: int(3),
    },
  },
}

TestnetLoans = {
  LoanType.GENERAL: 147173131,
  LoanType.STABLECOIN_EFFICIENCY: 147173190,
  LoanType.ALGO_EFFICIENCY: 168153622,
  LoanType.ULTRASWAP_UP: 397181473,
  LoanType.ULTRASWAP_DOWN: 397181998,
}

TESTNET_RESERVE_ADDRESS = "KLF3MEIIHMTA7YHNPLBDVHLN2MVC27X5M7ULTDZLMEX5XO5XCUP7HGBHMQ"

TestnetOracle = {
  'oracle0AppId': 159512493,
  'oracleAdapterAppId': 147153711,
  'decimals': 14,
}

TestnetOpUp = {
  'callerAppId': 397104542,
  'baseAppId': 118186203,
}
