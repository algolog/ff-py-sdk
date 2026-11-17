from ffsdk.client import FFMainnetClient
from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import assign_group_id
from algosdk.account import address_from_private_key
from algosdk.signer import PQAlgorandSigner, Falcon1024AlgorandSigner
from algosdk.atomic_transaction_composer import AccountTransactionSigner
from ffsdk.state_utils import AlgodIndexerCombo
from ffsdk.lend.datatypes import LoanType, Account
from ffsdk.lend.loan import (
    retrieveLoanInfo,
    prepareCreateUserLoan,
)
from ffsdk.transaction_utils import transferAlgoOrAsset
from ffutils import ask_sign_and_send
from ffsdk.config import USER_TXN_FEE
from algorand_falcon import falcon1024
import argparse

USER_ACCOUNT = Account(addr="", sk="")

if len(USER_ACCOUNT.sk) == falcon1024.PRIVATE_KEY_SIZE:
    raw_signer = falcon1024.Signer(USER_ACCOUNT.sk)
    user_signer = Falcon1024AlgorandSigner(raw_signer.public_key, raw_signer.sign)
    signing_address = user_signer.address
else:
    user_signer = AccountTransactionSigner(USER_ACCOUNT.sk)
    signing_address = address_from_private_key(USER_ACCOUNT.sk)


parser = argparse.ArgumentParser(
    description="Create new loan escrow",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("-l", "--ltype", type=int, default=0, help="Loan type (int from LoanType enum)")
parser.add_argument("-n", "--dry-run", action="store_true", help="Simulate transactions instead of sending")
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
print(f"signing addres: {signing_address}")
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

if isinstance(user_signer, PQAlgorandSigner):
    params.flat_fee = True
    params.fee = USER_TXN_FEE

fund_txn = transferAlgoOrAsset(
    0, user_address, escrow.addr, ESCROW_FUND_AMOUNT, params
)

unsigned_txns = [fund_txn] + create_txns

# Prepare a transaction group
txn_group = assign_group_id(unsigned_txns)

ask_sign_and_send(
    algod,
    txn_group,
    user_signer,
    extra_sign={AccountTransactionSigner(escrow.sk): [2]},
    simulate=args.dry_run,
)
