from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import Transaction, write_to_file, wait_for_confirmation
from algosdk.atomic_transaction_composer import (
    TransactionSigner,
    sign_transaction_with_signer,
)


def ask_sign_and_send(
    algod: AlgodClient,
    txn_group: list[Transaction],
    signer: TransactionSigner,
    extra_sign: dict[TransactionSigner, list[int]] | None = None,
    simulate: bool = False,
):
    """Ask user permission to proceed, sign and send transaction group.

    :param algod: Algod client
    :param txn_group: transaction group to sign and send
    :param signer: transactions signer
    :param extra_sign: optional map signer->txn_idx_list for
                       signing some of the transactions with another key(s)
    :param simulate: bool, simulate transactions instead of sending (default: False)
    """

    proceed_ask = input("Proceed (y/N)?: ").lower()
    do_proceed = True if proceed_ask in ["y", "yes"] else False

    if do_proceed:
        print("Sending  transaction...")

        # Sign the group
        signed_txns = [sign_transaction_with_signer(txn, signer) for txn in txn_group]
        if extra_sign is not None:
            # Re-sign some txns with another signer
            for other_signer, indexes in extra_sign.items():
                for n in indexes:
                    signed_txns[n] = sign_transaction_with_signer(
                        txn_group[n], other_signer
                    )

        if simulate:
            res = algod.simulate_raw_transactions(signed_txns)
            rg0 = res["txn-groups"][0]
            print("Failed at:", rg0.get("failed-at"))
            print("Failure msg:", rg0.get("failure-message"))
        else:
            # Send
            try:
                txid = algod.send_transactions(signed_txns)
                wait_for_confirmation(algod, txid)
                print(f"Txid {txid} confirmed.")
            except Exception as e:
                print(e)
