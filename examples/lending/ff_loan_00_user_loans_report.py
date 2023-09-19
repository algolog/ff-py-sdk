from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lending.v2.datatypes import LoanType
from ffsdk.lending.v2.loan import retrieveUserLoansInfo
from ffutils import user_loan_report
import argparse


parser = argparse.ArgumentParser(description="Show report of account loans")
parser.add_argument("user_address")
args = parser.parse_args()

algod_address = "https://mainnet-api.algonode.cloud"
algod_token = ""
algod = AlgodClient(algod_token, algod_address)
indexer = AlgodIndexerCombo(algod, "", "https://mainnet-idx.algonode.cloud")
client = FFMainnetClient(algod, indexer).lending

user_address = args.user_address
print(f"account: {user_address}")

# loans report
for ltype in LoanType:
    userLoansInfo = retrieveUserLoansInfo(
        client.indexer,
        client.loans[ltype],
        client.pool_manager_app_id,
        client.oracle,
        user_address,
    )
    for loan in userLoansInfo:
        user_loan_report(loan, ltype, client.pools)
