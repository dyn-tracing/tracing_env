import logging
from pathlib import Path

import pytest
import kubernetes_env.util as util
import kubernetes_env.kube_env as kube_env

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
SIM_DIR = FILE_DIR.joinpath("tracing_sim")
COMPILER_DIR = FILE_DIR.joinpath("tracing_compiler")
ENV_DIR = FILE_DIR.joinpath("kubernetes_env")
COMPILER_BINARY = COMPILER_DIR.joinpath("target/debug/dtc")
QUERY_DIR = COMPILER_DIR.joinpath("example_queries")
UDF_DIR = COMPILER_DIR.joinpath("example_udfs")

QUERIES = [
    ("count.cql", ["count.cc"]),
    ("breadth_histogram.cql", ["histogram.cc"]),
    ("height_histogram.cql", ["histogram.cc"]),
    ("response_code_count.cql", ["count.cc"]),
    ("response_size_avg.cql", ["avg.cc"]),
    ("return.cql", []),
    ("return_height.cql", []),
]
# test names
IDS = [i[0] for i in QUERIES]


class TestClassKubernetes:
    @classmethod
    def setup_class(cls):
        """ setup any state specific to the execution of the given class (which
        usually contains tests).
        """
        result = kube_env.setup_bookinfo_deployment("MK", False)
        assert result == util.EXIT_SUCCESS
        # start the modified bookinfo app, ignore the result for now
        result = kube_env.install_modded_bookinfo()

    @pytest.mark.parametrize("query_file,query_udfs", QUERIES, ids=IDS)
    def test_deployment(self, query_file, query_udfs):
        # generate the filter code
        cmd = f"{COMPILER_BINARY} "
        cmd += f"-q {QUERY_DIR.joinpath(query_file)} "
        for query_udf in query_udfs:
            udf_file = UDF_DIR.joinpath(query_udf)
            cmd += f"-u {udf_file} "
        result = util.exec_process(cmd)
        assert result == util.EXIT_SUCCESS
        # build the filter
        result = kube_env.build_filter(kube_env.FILTER_DIR)
        assert result == util.EXIT_SUCCESS
        # deploy the filter
        result = kube_env.refresh_filter(kube_env.FILTER_DIR)
        assert result == util.EXIT_SUCCESS

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a call to
        setup_class.
        """
        kube_env.stop_kubernetes("MK")


class Simulator:
    pass
