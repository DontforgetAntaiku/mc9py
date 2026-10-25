import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("MC9_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="needs MC9 in the sandbox: set MC9_INTEGRATION=1")
    for item in items:
        if "mc9" in item.keywords:
            item.add_marker(skip)


def pytest_generate_tests(metafunc):
    """MC9 integration tests run once per engine: the click engine and the native (mc9hook.dll) engine."""
    if metafunc.definition.get_closest_marker("mc9"):
        metafunc.fixturenames.append("engine")
        metafunc.parametrize("engine", ["clicks", "native"], indirect=True)


@pytest.fixture
def engine(request):
    import mc9
    old = mc9.config.engine
    mc9.config.engine = request.param
    yield request.param
    mc9.config.engine = old


@pytest.fixture(autouse=True)
def _no_mc9_in_offline_tests(request):
    """Offline tests must never start MC9 (e.g. to learn an unknown part)."""
    import mc9
    old = mc9.config.learn_parts
    if not request.node.get_closest_marker("mc9"):
        mc9.config.learn_parts = False
    yield
    mc9.config.learn_parts = old
