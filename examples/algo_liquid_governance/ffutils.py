from algosdk.v2client.algod import AlgodClient
from algosdk.transaction import Transaction, write_to_file, wait_for_confirmation


def ask_sign_and_send(
    algod: AlgodClient,
    txn_group: list[Transaction],
    sk: str,
    extra_sign=None,
    simulate=False,
):
    """Ask user permission to proceed, sign and send transaction group.

    :param algod: Algod client
    :param txn_group: transaction group to sign and send
    :param sk: secret key for signing transactions
    :param extra_sign: dict[int, str], optional dictionary transaction_number->secret_key for
                       signing some of the transactions with another key(s)
    :param simulate: bool, simulate transactions instead of sending (default: False)
    """

    proceed_ask = input("Proceed (y/N)?: ").lower()
    do_proceed = True if proceed_ask in ["y", "yes"] else False

    if do_proceed:
        print("Sending  transaction...")

        # Sign the group
        signed_txns = [txn.sign(sk) for txn in txn_group]
        if extra_sign is not None:
            for n in extra_sign:
                signed_txns[n] = signed_txns[n].transaction.sign(extra_sign[n])

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
