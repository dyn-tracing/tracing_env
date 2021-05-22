import logging
from pathlib import Path

import pytest
import kubernetes_env.kube_util as util
import kubernetes_env.kube_env as kube_env
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

class TestClassKubernetes:
    @classmethod
    def setup_class(cls):
        """ Setup any state specific to the execution of the given class (which
        usually contains tests).
        """
        result = kube_env.setup_application_deployment("MK", False, "BK")
        assert result == util.EXIT_SUCCESS

    def test_return_height(self):
        result = query_tests.test_height("MK")
        assert result == util.EXIT_SUCCESS

    def test_get_service_name(self):
        result = query_tests.test_get_service_name("MK")
        assert result == util.EXIT_SUCCESS

    def test_get_service_name_distributed(self):
        result = query_tests.test_get_service_name("MK", True)
        assert result == util.EXIT_SUCCESS

    def test_request_size(self):
        result = query_tests.test_request_size("MK")
        assert result == util.EXIT_SUCCESS

    def test_request_time(self):
        result = query_tests.test_request_time("MK")
        assert result == util.EXIT_SUCCESS

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a call to
        setup_class.
        """
        kube_env.stop_kubernetes("MK")
