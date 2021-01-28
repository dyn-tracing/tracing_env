#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from shutil import copytree, rmtree

import kubernetes_env.kube_util as util

FILE_DIR = Path.resolve(Path(__file__)).parent
SIM_DIR = FILE_DIR.joinpath("tracing_sim")
COMPILER_DIR = FILE_DIR.joinpath("tracing_compiler")
COMPILER_BINARY = COMPILER_DIR.joinpath("target/debug/dtc")
QUERY_DIR = COMPILER_DIR.joinpath("example_queries")
UDF_DIR = COMPILER_DIR.joinpath("example_udfs")

log = logging.getLogger(__name__)


def check_filter(query_file, query_udfs):
    filter_dir = COMPILER_DIR.joinpath("rust_filter")
    target_filter_dir = SIM_DIR.joinpath("libs/rust_filter")

    # generate the filter code
    cmd = f"{COMPILER_BINARY} "
    cmd += f"-q {QUERY_DIR.joinpath(query_file)} "
    for query_udf in query_udfs:
        udf_file = UDF_DIR.joinpath(query_udf)
        udf_file = udf_file.with_suffix(".rs")
        cmd += f"-u {udf_file} "
    cmd += f"-o {filter_dir.joinpath('filter.rs')} "
    # generate code for the simulator
    cmd += "-c sim "
    cmd += "-r 0 "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result

    # move the directory in the simulator directory
    rmtree(target_filter_dir, ignore_errors=True)
    copytree(filter_dir, target_filter_dir)

    # build the filter
    cmd = "cargo build "
    cmd += f"--manifest-path {target_filter_dir}/Cargo.toml"
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result

    # run the filter in the simulator
    cmd = f"cargo run --manifest-path {SIM_DIR}/Cargo.toml -- "
    cmd += f"-p {target_filter_dir}/target/debug/librust_filter"
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result
    # cleanup
    rmtree(target_filter_dir)
    return util.EXIT_SUCCESS


def main(args):
    check_filter(args.query_file, args.query_udfs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log-file", dest="log_file",
                        default="filter_test.log",
                        help="Specifies name of the log file.")
    parser.add_argument("-ll", "--log-level", dest="log_level",
                        default="INFO",
                        choices=["CRITICAL", "ERROR", "WARNING",
                                 "INFO", "DEBUG", "NOTSET"],
                        help="The log level to choose.")
    parser.add_argument("-qf", "--query-file", dest="query_file",
                        required=True,
                        help="The query to compile with the simulator")
    parser.add_argument('-qu', '--query-udfs', nargs='+', dest="query_udfs",
                        help="List of UDFs needed for the query.",
                        default=[])
    # Parse options and process argv
    arguments = parser.parse_args()
    # configure logging
    logging.basicConfig(filename=arguments.log_file,
                        format="%(levelname)s:%(message)s",
                        level=getattr(logging, arguments.log_level),
                        filemode="w")
    stderr_log = logging.StreamHandler()
    stderr_log.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
    logging.getLogger().addHandler(stderr_log)
    main(arguments)
