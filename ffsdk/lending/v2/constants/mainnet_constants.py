from ..datatypes import LPTokenProvider, LoanType
from ..mathlib import ONE_4_DP

MAINNET_POOL_MANAGER_APP_ID = 971350278

MAINNET_DEPOSITS_APP_ID = 971353536

MAINNET_DEPOSIT_STAKING_APP_ID = 1093729103

# type MainnetPoolKey = "ALGO" | "gALGO" | "USDC" | "USDt" | "GARD" | "goBTC" | "goETH" | "WBTC" | "WETH" | "WAVAX" | "WSOL"| "WLINK"| "OPUL" | "WMPL";
MainnetPools = {
  'ALGO': {
    'appId': 971368268,
    'assetId': 0,
    'fAssetId': 971381860,
    'frAssetId': 971381861,
    'assetDecimals': 6,
    'poolManagerIndex': 0,
    'loans': {
      971388781: int(0),
      971389489: int(0),
      1202382736: int(1),
      1202382829: int(1),
    },
  },
  'gALGO': {
    'appId': 971370097,
    'assetId': 793124631,
    'fAssetId': 971383839,
    'frAssetId': 971383840,
    'assetDecimals': 6,
    'poolManagerIndex': 1,
    'loans': {
      971388781: int(1),
      971389489: int(1),
    },
  },
  'USDC': {
    'appId': 971372237,
    'assetId': 31566704,
    'fAssetId': 971384592,
    'frAssetId': 971384593,
    'assetDecimals': 6,
    'poolManagerIndex': 2,
    'loans': {
      971388781: int(2),
      971388977: int(0),
      1202382736: int(0),
      1202382829: int(0),
    },
  },
  'USDt': {
    'appId': 971372700,
    'assetId': 312769,
    'fAssetId': 971385312,
    'frAssetId': 971385313,
    'assetDecimals': 6,
    'poolManagerIndex': 3,
    'loans': {
      971388781: int(3),
      971388977: int(1),
    },
  },
  'GARD': {
    'appId': 1060585819,
    'assetId': 684649988,
    'fAssetId': 1060587336,
    'frAssetId': 1060587337,
    'assetDecimals': 6,
    'poolManagerIndex': 7,
    'loans': {
      971388781: int(7),
      971388977: int(2),
    },
  },
  'goBTC': {
    'appId': 971373361,
    'assetId': 386192725,
    'fAssetId': 971386173,
    'frAssetId': 971386174,
    'assetDecimals': 8,
    'poolManagerIndex': 4,
    'loans': {
      971388781: int(4),
      1202382736: int(2),
      1202382829: int(2),
    },
  },
  'goETH': {
    'appId': 971373611,
    'assetId': 386195940,
    'fAssetId': 971387073,
    'frAssetId': 971387074,
    'assetDecimals': 8,
    'poolManagerIndex': 5,
    'loans': {
      971388781: int(5),
      1202382736: int(3),
      1202382829: int(3),
    },
  },
  'WBTC': {
    'appId': 1067289273,
    'assetId': 1058926737,
    'fAssetId': 1067295154,
    'frAssetId': 1067295155,
    'assetDecimals': 8,
    'poolManagerIndex': 8,
    'loans': {
      971388781: int(8),
      1202382736: int(4),
      1202382829: int(4),
    },
  },
  'WETH': {
    'appId': 1067289481,
    'assetId': 887406851,
    'fAssetId': 1067295558,
    'frAssetId': 1067295559,
    'assetDecimals': 8,
    'poolManagerIndex': 9,
    'loans': {
      971388781: int(9),
      1202382736: int(5),
      1202382829: int(5),
    },
  },
  'WAVAX': {
    'appId': 1166977433,
    'assetId': 893309613,
    'fAssetId': 1166979636,
    'frAssetId': 1166979637,
    'assetDecimals': 8,
    'poolManagerIndex': 10,
    'loans': {
      971388781: int(10),
    },
  },
  'WSOL': {
    'appId': 1166980669,
    'assetId': 887648583,
    'fAssetId': 1166980820,
    'frAssetId': 1166980821,
    'assetDecimals': 8,
    'poolManagerIndex': 11,
    'loans': {
      971388781: int(11),
    },
  },
  'WLINK': {
    'appId': 1216434571,
    'assetId': 1200094857,
    'fAssetId': 1216437148,
    'frAssetId': 1216437149,
    'assetDecimals': 8,
    'poolManagerIndex': 13,
    'loans': {
      971388781: int(13),
    },
  },
  'OPUL': {
    'appId': 1044267181,
    'assetId': 287867876,
    'fAssetId': 1044269355,
    'frAssetId': 1044269356,
    'assetDecimals': 10,
    'poolManagerIndex': 6,
    'loans': {
      971388781: int(6),
    }
  },
  'WMPL': {
    'appId': 1166982094,
    'assetId': 1163259470,
    'fAssetId': 1166982296,
    'frAssetId': 1166982297,
    'assetDecimals': 8,
    'poolManagerIndex': 12,
    'loans': {
      971388781: int(12),
    },
  },
}

MainnetLoans = {
  LoanType.GENERAL: 971388781,
  LoanType.STABLECOIN_EFFICIENCY: 971388977,
  LoanType.ALGO_EFFICIENCY: 971389489,
  LoanType.ULTRASWAP_UP: 1202382736,
  LoanType.ULTRASWAP_DOWN: 1202382829,
}

# type MainnetLendingPoolKey = "ALGOUSDCPLP" | "ALGOgALGOPLP" | "ALGOwBTCPLP" | "ALGOwETHPLP" | "ALGOwAVAXPLP" | "ALGOwSOLPLP" | "ALGOwLINKPLP" | "ALGOwMPLPLP" | "USDCUSDtPLP";
MainnetLendingPools = {
  'ALGOUSDCPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1116363704,
    'lpAssetId': 1116363710,
    'pool0AppId': 971368268,
    'pool1AppId': 971372237,
    'asset0Id': 0,
    'asset1Id': 31566704,
    'feeScale': ONE_4_DP,
  },
  'ALGOgALGOPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1116366345,
    'lpAssetId': 1116366351,
    'pool0AppId': 971368268,
    'pool1AppId': 971370097,
    'asset0Id': 0,
    'asset1Id': 793124631,
    'feeScale': ONE_4_DP,
  },
  'ALGOwBTCPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1116367260,
    'lpAssetId': 1116367266,
    'pool0AppId': 971368268,
    'pool1AppId': 1067289273,
    'asset0Id': 0,
    'asset1Id': 1058926737,
    'feeScale': ONE_4_DP,
  },
  'ALGOwETHPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1116369904,
    'lpAssetId': 1116369910,
    'pool0AppId': 971368268,
    'pool1AppId': 1067289481,
    'asset0Id': 0,
    'asset1Id': 887406851,
    'feeScale': ONE_4_DP,
  },
  'ALGOwAVAXPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1168319565,
    'lpAssetId': 1168319571,
    'pool0AppId': 971368268,
    'pool1AppId': 1166977433,
    'asset0Id': 0,
    'asset1Id': 893309613,
    'feeScale': ONE_4_DP,
  },
  'ALGOwSOLPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1168322128,
    'lpAssetId': 1168322134,
    'pool0AppId': 971368268,
    'pool1AppId': 1166980669,
    'asset0Id': 0,
    'asset1Id': 887648583,
    'feeScale': ONE_4_DP,
  },
  'ALGOwLINKPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1217112826,
    'lpAssetId': 1217112832,
    'pool0AppId': 971368268,
    'pool1AppId': 1216434571,
    'asset0Id': 0,
    'asset1Id': 1200094857,
    'feeScale': ONE_4_DP,
  },
  'ALGOwMPLPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1168322907,
    'lpAssetId': 1168322913,
    'pool0AppId': 971368268,
    'pool1AppId': 1166982094,
    'asset0Id': 0,
    'asset1Id': 1163259470,
    'feeScale': ONE_4_DP,
  },
  'USDCUSDtPLP': {
    'provider': LPTokenProvider.PACT,
    'lpPoolAppId': 1116364721,
    'lpAssetId': 1116364727,
    'pool0AppId': 971372237,
    'pool1AppId': 971372700,
    'asset0Id': 31566704,
    'asset1Id': 312769,
    'feeScale': ONE_4_DP,
  },
}

MAINNET_RESERVE_ADDRESS = "Q5Q5FC5PTYQIUX5PGNTEW22UJHJHVVUEMMWV2LSG6MGT33YQ54ST7FEIGA"

MainnetOracle = {
  'oracle0AppId': 1040271396,
  'oracle1AppId': 971323141,
  'oracleAdapterAppId': 971333964,
  'decimals': 14,
}

MainnetOpUp = {
  'callerAppId': 1167143153,
  'baseAppId': 971335616,
}

MainnetPactLPFarms = {
    'ALGOUSDCPLP': 1124031333,
    'ALGOgALGOPLP': 1124036810,
    'ALGOwBTCPLP': 1124037645,
    'ALGOwETHPLP': 1124038236,
    'ALGOwAVAXPLP': 1170254199,
    'ALGOwSOLPLP': 1177033931,
    'ALGOwMPLPLP': 1180923632,
    'USDCUSDtPLP': 1124035184,
}
