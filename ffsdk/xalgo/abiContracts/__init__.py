import os
from algosdk.abi import Contract


def load_contract(fname_json: str) -> Contract:
    """Loads ABI contract from JSON file in the current direrctory"""
    path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(path, fname_json), "r") as f:
        contract = Contract.from_json(f.read())
    return contract


xAlgoABIContract = load_contract("xalgo.json")
