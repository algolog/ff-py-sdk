# ff-py-sdk
Some functions from the [folks-finance-js-sdk](https://github.com/Folks-Finance/folks-finance-js-sdk) translated to Python. Unofficial Python SDK for the [Folks Finance](https://folks.finance) v2 lending protocol on the Algorand blockchain.

* Work in progress, use at your own risk.
* Function names and arguments are preserved from the JS SDK. Camel case and snake case code styles are sometimes mixed.

## Progress overview

### Lending
<details>
<summary>State retrieval functions</summary>

* Deposit
    - [x] `retrievePoolManagerInfo`
    - [x] `retrievePoolInfo`
    - [x] `retrieveUserDepositsInfo`
    - [x] `retrieveUserDepositsFullInfo`
    - [x] `retrieveUserDepositInfo`

* DepositStaking
    - [x] `retrieveDepositStakingInfo`
    - [x] `retrieveUserDepositStakingsLocalState`
    - [x] `retrieveUserDepositStakingLocalState`

* Loan
    - [x] `retrieveLoanInfo`
    - [x] `retrieveLoansLocalState`
    - [x] `retrieveLoanLocalState`
    - [x] `retrieveUserLoansInfo`
    - [x] `retrieveUserLoanInfo`
    - [x] `retrieveLiquidatableLoans`
    - [x] `getMaxReduceCollateralForBorrowUtilisationRatio`
    - [x] `getMaxBorrowForBorrowUtilisationRatio`
    - [x] `getUserLoanAssets` *NEW*

* Oracle
    - [x] `parseOracleValue`
    - [ ] `parseLPTokenOracleValue`
    - [ ] `getTinymanLPPrice`
    - [ ] `getPactLPPrice`
    - [x] `getOraclePrices` (partial, without LP tokens)

* Utils
    - [x] `getEscrows`
    - [x] `getAppEscrowsWithState` *NEW*
    - [x] `depositStakingLocalState`
    - [x] `depositStakingProgramsInfo`
    - [x] `userDepositStakingInfo`
    - [x] `loanLocalState`
    - [x] `userLoanInfo`

* AMM
    - [x] `retrievePactLendingPoolInfo` (TODO: farming APRs)
</details>

<details>
<summary>Transaction preparation functions</summary>

* Deposit
    - [x] `prepareAddDepositEscrowToDeposits`
    - [x] `prepareOptDepositEscrowIntoAssetInDeposits`
    - [x] `prepareDepositIntoPool`
    - [x] `prepareWithdrawFromDepositEscrowInDeposits`
    - [x] `prepareWithdrawFromPool`
    - [x] `prepareUpdatePoolInterestIndexes`
    - [x] `prepareOptOutDepositEscrowFromAssetInDeposits`
    - [x] `prepareRemoveDepositEscrowFromDeposits`

* Deposit Staking
    - [x] `prepareAddDepositStakingEscrow`
    - [x] `prepareOptDepositStakingEscrowIntoAsset`
    - [x] `prepareSyncStakeInDepositStakingEscrow`
    - [x] `prepareClaimRewardsOfDepositStakingEscrow`
    - [x] `prepareWithdrawFromDepositStakingEscrow`
    - [x] `prepareOptOutDepositStakingEscrowFromAsset`
    - [x] `prepareRemoveDepositStakingEscrow`
 
 * Loan
    - [x] `prepareCreateUserLoan`
    - [x] `prepareAddCollateralToLoan`
    - [x] `prepareSyncCollateralInLoan`
    - [x] `prepareReduceCollateralFromLoan`
    - [ ] `prepareSwapCollateralInLoanBegin`
    - [ ] `prepareSwapCollateralInLoanEnd`
    - [x] `prepareRemoveCollateralFromLoan`
    - [x] `prepareBorrowFromLoan`
    - [x] `prepareSwitchBorrowTypeInLoan`
    - [x] `prepareRepayLoanWithTxn`
    - [x] `prepareRepayLoanWithCollateral`
    - [x] `prepareLiquidateLoan`
    - [ ] `prepareRebalanceUpLoan`
    - [ ] `prepareRebalanceDownLoan`
    - [x] `prepareRemoveUserLoan`
    - [ ] `prepareFlashLoanBegin`
    - [ ] `prepareFlashLoanEnd`
    - [ ] `wrapWithFlashLoan`

 * Oracle
    - [x] `prepareRefreshPricesInOracleAdapter` (partial, without LPPools oracle update)
</details>

### Algo liquid governance
<details>
<summary>State retrieval functions</summary>

 * Common
    - [x] `getDispenserInfo`

 * Governance v2
    - [x] `getDistributorLogicSig`
    - [x] `getDistributorInfo`
    - [x] `getUserLiquidGovernanceInfo`
    - [x] `getEscrowGovernanceStatus`
</details>

<details>
<summary>Transaction preparation functions</summary>
 
 * Governance v2
   
    - [ ] `prepareAddLiquidGovernanceEscrowTransactions`
    - [x] `prepareMintTransactions`
    - [x] `prepareUnmintPremintTransaction`
    - [x] `prepareUnmintTransactions`
    - [x] `prepareClaimPremintTransaction`
    - [x] `prepareRegisterEscrowOnlineTransaction`
    - [x] `prepareRegisterEscrowOfflineTransaction`
    - [x] `prepareCommitOrVoteTransaction`
    - [ ] `prepareRemoveLiquidGovernanceEscrowTransactions`
    - [x] `prepareBurnTransactions`
</details>

## Installation

`pip install git+https://github.com/algolog/ff-py-sdk`

## Example
```python
from ffsdk.client import FFMainnetClient
from ffsdk.lending.v2.deposit import retrievePoolManagerInfo, retrievePoolInfo
from ffsdk.lending.v2.depositStaking import retrieveDepositStakingInfo
from ffsdk.lending.v2.utils import depositStakingProgramsInfo
from ffsdk.lending.v2.oracle import getOraclePrices
from ffsdk.lending.v2.mathlib import ONE_14_DP


client = FFMainnetClient().lending
pmi = retrievePoolManagerInfo(client.indexer, client.pool_manager_app_id)
oracle_prices = getOraclePrices(client.indexer, client.oracle)

# deposit pool info
pool_info = retrievePoolInfo(client.indexer, client.pools["ALGO"])
deposit_yield = pool_info.interest.depositInterestYield / ONE_14_DP
print(f'ALGO deposit APY: {deposit_yield:.2f}%')

# deposit staking programs info
dsi = retrieveDepositStakingInfo(client.indexer, client.deposit_staking_app_id)
dpi = depositStakingProgramsInfo(dsi, pmi, client.pools, oracle_prices)
```
