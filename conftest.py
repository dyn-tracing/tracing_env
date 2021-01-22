
import pytest



@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):
    outcome = yield
    report = outcome.get_result()
    report.custom_err = getattr(item, 'custom_err', 0)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "run_default: Default tests to run"
    )


def pytest_collection_modifyitems(items, config):

    # Ensure the `run_default` marker is always selected for
    markexpr = config.getoption("markexpr", "False")
    keyword = config.getoption("keyword", "False")
    if keyword:
        config.option.keyword = keyword
    elif markexpr:
        config.option.markexpr = markexpr
    else:
        config.option.markexpr = f"run_default"
