import logging
from pathlib import Path

import pytest
import kubernetes_env.kube_util as util
import kubernetes_env.kube_env as kube_env
from check_filter import check_filter
import query_tests

# configure logging
log = logging.getLogger(__name__)
logging.basicConfig(filename="test.log",
                    format="%(levelname)s:%(message)s",
                    level=logging.INFO,
                    filemode='w')
stderr_log = logging.StreamHandler()
stderr_log.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
logging.getLogger().addHandler(stderr_log)

# some folder definitions
FILE_DIR = Path.resolve(Path(__file__)).parent
COMPILER_DIR = FILE_DIR.joinpath("tracing_compiler")
COMPILER_BINARY = COMPILER_DIR.joinpath("target/debug/dtc")
QUERY_DIR = COMPILER_DIR.joinpath("example_queries")
UDF_DIR = COMPILER_DIR.joinpath("example_udfs")

class TestClassKubernetes:
    @classmethod
    def setup_class(cls):
        """ setup any state specific to the execution of the given class (which
        usually contains tests).
        """
        result = kube_env.setup_bookinfo_deployment("MK", False)
        assert result == util.EXIT_SUCCESS
        # start the modified bookinfo app, ignore the result for now
        result = kube_env.deploy_bookinfo()


    def test_count(self):
        result = query_tests.test_count()
        assert result == util.EXIT_SUCCESS

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a call to
        setup_class.
        """
        kube_env.stop_kubernetes("MK")
