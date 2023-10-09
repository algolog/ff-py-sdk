# MIT License
# Copyright (c) 2021 Algofi, Inc.

# IMPORTS
from algosdk.v2client.indexer import IndexerClient
from base64 import b64decode
from .config import ALGO_ASSET_ID


class AlgodIndexerCombo(IndexerClient):
    """
    Wraps AlgodClient and uses it to handle most indexer queries.
    Code example from https://github.com/Algofiorg/algofi-py-sdk/issues/32
    """

    def __init__(self, algod, indexer_token, indexer_address, headers=None):
        super().__init__(indexer_token, indexer_address, headers)
        self.algod = algod

    def account_info(self, address, round_num=None, exclude=None):
        return {"account": self.algod.account_info(address, exclude=None)}

    def applications(self, app_id, round_num=None):
        return {"application": self.algod.application_info(app_id)}

    def asset_info(self, asset_id):
        return {"asset": self.algod.asset_info(asset_id)}

    def application_boxes(self, app_id, next_page=None):
        return {
            "application-id": app_id,
            "boxes": self.algod.application_boxes(app_id)["boxes"],
        }


# FUNCTIONS


def format_state(state, decode_byte_values=False, decode_byte_keys=True):
    """Format state dict by base64 decoding keys and, optionally, bytes values.

    :param state: state dict of base64 key -> dict
    :type state: dict
    :param decode_byte_values: whether to decode base64 bytes values to utf-8
    :type decode_byte_values: bool
    :return: formatted state dict
    :rtype: dict
    """

    formatted_state = {}
    for item in state:
        key = item["key"]
        value = item["value"]
        if decode_byte_keys:
            try:
                formatted_key = b64decode(key).decode("utf-8")
            except:
                formatted_key = b64decode(key)
        else:
            formatted_key = b64decode(key)

        if value["type"] == 1:
            # byte string
            if decode_byte_values:
                try:
                    formatted_state[formatted_key] = b64decode(value["bytes"]).decode(
                        "utf-8"
                    )
                except:
                    formatted_state[formatted_key] = value["bytes"]
            else:
                formatted_state[formatted_key] = value["bytes"]
        else:
            # integer
            formatted_state[formatted_key] = value["uint"]
    return formatted_state


def get_local_states(indexer, address, decode_byte_values=False, block=None):
    """Get local state of user for all opted in apps.

    :param indexer: algorand indexer
    :type indexer: :class:`IndexerClient`
    :param address: user address
    :type address: str
    :param decode_byte_values: whether to base64 decode bytes values
    :type decode_byte_values: bool
    :param block: block at which to query local state
    :type block: int, optional
    :return: formatted local state dict
    :rtype: dict
    """

    try:
        results = indexer.account_info(
            address, round_num=block, exclude="assets,created-apps,created-assets"
        ).get("account", {})
    except:
        raise Exception("Account does not exist.")

    result = {}
    if "apps-local-state" in results:
        for local_state in results["apps-local-state"]:
            result[local_state["id"]] = format_state(
                local_state.get("key-value", []), decode_byte_values=decode_byte_values
            )
    return result


def get_local_state_at_app(
    indexer, app_id, address, decode_byte_values=False, block=None
):
    """Get local state of user for given app.

    :param indexer: algorand indexer
    :type indexer: :class:`IndexerClient`
    :param app_id: app id
    :type app_id: int
    :param address: user address
    :type address: str
    :param decode_byte_values: whether to base64 decode bytes values
    :type decode_byte_values: bool
    :param block: block at which to query local state
    :type block: int, optional
    :return: formatted local state dict
    :rtype: dict
    """

    local_states = get_local_states(
        indexer, address, decode_byte_values=decode_byte_values, block=block
    )
    if app_id in local_states:
        return local_states[app_id]
    else:
        return None


def get_global_state(
    indexer, app_id, decode_byte_values=False, decode_byte_keys=True, block=None
):
    """Get global state of a given application.

    :param indexer: algorand indexer
    :type indexer: :class:`IndexerClient`
    :param app_id: app id
    :type app_id: int
    :param decode_byte_values: whether to base64 decode bytes values
    :type decode_byte_values: bool
    :param block: block at which to query global state
    :type block: int, optional
    :return: formatted global state dict
    :rtype: dict
    """

    try:
        application_info = indexer.applications(app_id, round_num=block).get(
            "application", {}
        )
    except:
        raise Exception("Application does not exist.")
    return format_state(
        application_info["params"]["global-state"],
        decode_byte_values=decode_byte_values,
        decode_byte_keys=decode_byte_keys,
    )


def get_balances(indexer, address, block=None):
    """Get balances for a given user.

    :param indexer: algorand indexer client
    :type indexer: :class:`IndexerClient`
    :param address: user address
    :type address: str
    :param block: block at which to query balances
    :type block: int, optional
    :return: dict of asset id -> amount
    :rtype: dict
    """

    balances = {}
    account_info = indexer.account_info(address, round_num=block)["account"]
    balances[ALGO_ASSET_ID] = account_info["amount"]
    if "assets" in account_info:
        for asset_info in account_info["assets"]:
            balances[asset_info["asset-id"]] = asset_info["amount"]
    return balances


def get_accounts_opted_into_app(indexer, app_id, exclude=None):
    """Iterator over accounts opted into a given app

    :param indexer: algorand indexer
    :type indexer: :class:`IndexerClient`
    :param app_id: app id
    :type app_id: int
    :param exclude: comma-delimited list of information to exclude from indexer call
    :type exclude: str, optional
    :return: iterator over accounts
    :rtype: Iterator[dict]
    """

    next_page = ""
    while next_page is not None:
        accounts_interim = indexer.accounts(
            next_page=next_page, limit=1000, application_id=app_id, exclude=exclude
        )
        for account in accounts_interim.get("accounts", []):
            yield account
        next_page = accounts_interim.get("next-token", None)


def parse_uint64s(base64_value: str) -> list[int]:
    value = b64decode(base64_value).hex()
    # uint64s are 8 bytes each
    uint64s: list[int] = []
    i = 0
    while i < len(value):
        uint64s.append(int(value[i : i + 16], base=16))
        i += 16
    return uint64s


def parse_bits_as_booleans(base64_value: str) -> list[bool]:
    value = b64decode(base64_value).hex()
    # bits = ("00000000" + Number("0x" + value).toString(2)).slice(-8);
    bits = f"{int(value, base=16):08b}"[-8:]
    bools = [bool(int(c)) for c in bits]
    return bools
