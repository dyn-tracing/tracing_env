import logging
from pathlib import Path
from shutil import copytree, rmtree

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

KUBE_QUERIES = [
    pytest.param("count.cql", ["count"]),
    pytest.param("breadth_histogram.cql", ["histogram"]),
    pytest.param("height_histogram.cql", ["histogram"]),
    pytest.param("response_code_count.cql", ["count"]),
    pytest.param("response_size_avg.cql", ["avg"]),
    pytest.param("return.cql", []),
    pytest.param("return_height.cql", []),
]
# test names
KUBE_IDS = [i.values[0] for i in KUBE_QUERIES]

SIM_QUERIES = [
    pytest.param("count.cql", ["count"]),
    pytest.param("breadth_histogram.cql", [
                 "histogram"], marks=pytest.mark.xfail),
    pytest.param("height_histogram.cql", [
                 "histogram"], marks=pytest.mark.xfail),
    pytest.param("response_code_count.cql", ["count"]),
    pytest.param("response_size_avg.cql", ["avg"], marks=pytest.mark.xfail),
    pytest.param("return.cql", [], marks=pytest.mark.xfail),
    pytest.param("return_height.cql", [], marks=pytest.mark.xfail),
]
# test names
SIM_IDS = [i.values[0] for i in SIM_QUERIES]


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

    @pytest.mark.parametrize("query_file,query_udfs", KUBE_QUERIES, ids=KUBE_IDS)
    def test_deployment(self, query_file, query_udfs):
        # generate the filter code
        cmd = f"{COMPILER_BINARY} "
        cmd += f"-q {QUERY_DIR.joinpath(query_file)} "
        for query_udf in query_udfs:
            udf_file = UDF_DIR.joinpath(query_udf)
            udf_file = udf_file.with_suffix(".cc")
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


class TestClassSimulator:
    filter_dir = COMPILER_DIR.joinpath("rust_filter")
    target_filter_dir = SIM_DIR.joinpath("libs/rust_filter")

    @pytest.mark.run_default
    @pytest.mark.parametrize("query_file,query_udfs", SIM_QUERIES, ids=SIM_IDS)
    def test_deployment(self, query_file, query_udfs):
        # generate the filter code
        cmd = f"{COMPILER_BINARY} "
        cmd += f"-q {QUERY_DIR.joinpath(query_file)} "
        for query_udf in query_udfs:
            udf_file = UDF_DIR.joinpath(query_udf)
            udf_file = udf_file.with_suffix(".rs")
            cmd += f"-u {udf_file} "
        cmd += f"-o {self.filter_dir.joinpath('src/filter.rs')} "
        # generate code for the simulator
        cmd += "-c sim "
        result = util.exec_process(cmd)
        assert result == util.EXIT_SUCCESS

        # move the directory in the simulator directory
        rmtree(self.target_filter_dir, ignore_errors=True)
        copytree(self.filter_dir, self.target_filter_dir)

        # build the filter
        cmd = "cargo build "
        cmd += f"--manifest-path {self.target_filter_dir}/Cargo.toml"
        result = util.exec_process(cmd)
        assert result == util.EXIT_SUCCESS

        # run the filter in the simulator
        cmd = f"cargo run --manifest-path {SIM_DIR}/Cargo.toml -- "
        cmd += f"-p {self.target_filter_dir}/target/debug/librust_filter"
        result = util.exec_process(cmd)
        assert result == util.EXIT_SUCCESS
        # cleanup
        rmtree(self.target_filter_dir)
