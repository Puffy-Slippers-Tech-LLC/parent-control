"""Ubuntu serial credential/getty preparation through the shared Smoke proof.

The shared backend executes only Smoke's ready step. It never creates a serial
console, graphical worker or installation boundary, and releases no input.
"""
import fixture_transfer_qualification as transfer


def main(*, assets, selection):
    return transfer.main(assets=assets, selection=selection, serial=True)
