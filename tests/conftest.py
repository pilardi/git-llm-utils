import os


def pytest_addoption(parser):
    parser.addoption(
        "--cmd",
        action="store",
        default=f"{os.getcwd()}/dist/git-llm-utils",
        help="distribution command for running integration tests",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "unit: these are unit tests meant to be run against the source code"
    )
    config.addinivalue_line(
        "markers",
        "integration: these are integration tests only meant to be run against the installable package",
    )
