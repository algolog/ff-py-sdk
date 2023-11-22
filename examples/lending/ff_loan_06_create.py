from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import LoanType, Account
from ffsdk.lending.v2.loan import (
    retrieveLoanInfo,
    prepareCreateUserLoan,
)
from ffsdk.transaction_utils import transferAlgoOrAsset
from ffutils import ask_sign_and_send
import argparse

USER_ACCOUNT = Account(addr="", sk="")

parser = argparse.ArgumentParser(
    description="Create new loan escrow",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("-l", "--ltype", type=int, default=0, help="Loan type (int from LoanType enum)")
args = parser.parse_args()

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "https://mainnet-idx.algonode.cloud")
client = FFMainnetClient(algod, indexer).lending

# loan info
ltype = LoanType(args.ltype)
loan_app_id = client.loans[ltype]
loan_info = retrieveLoanInfo(client.indexer, loan_app_id)
market_by_id = {pool.appId: name for name, pool in client.pools.items()}
loan_pools = [market_by_id[pool_app_id] for pool_app_id in loan_info.pools]
user_address = USER_ACCOUNT.addr

# print report
print(f"user addres: {user_address}")
print(f"loan type: {ltype}")
print(f"loan pools: {loan_pools}")
print("Preparing create txns...")

# prepare txns
ESCROW_FUND_AMOUNT = 728_500
params = client.algod.suggested_params()

create_txns, escrow = prepareCreateUserLoan(
    loan_app_id,
    user_address,
    params,
)

print(f"new escrow address: {escrow.addr}")

fund_txn = transferAlgoOrAsset(0, user_address, escrow.addr, ESCROW_FUND_AMOUNT, params)

unsigned_txns = [fund_txn] + create_txns

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(algod, txn_group, USER_ACCOUNT.sk, extra_sign={2: escrow.sk}, simulate=True)
