import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("MC9_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="needs MC9 in the sandbox: set MC9_INTEGRATION=1")
    for item in items:
        if "mc9" in item.keywords:
            item.add_marker(skip)
