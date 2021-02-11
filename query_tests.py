#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

import kubernetes_env.kube_util as util
import kubernetes_env.kube_env as kube_env
import kubernetes_env.send_request as requests
import kubernetes_env.query_storage as storage

# some folder definitions
FILE_DIR = Path.resolve(Path(__file__)).parent
COMPILER_DIR = FILE_DIR.joinpath("tracing_compiler")
COMPILER_BINARY = COMPILER_DIR.joinpath("target/debug/dtc")
QUERY_DIR = COMPILER_DIR.joinpath("example_queries")
UDF_DIR = COMPILER_DIR.joinpath("example_udfs")

log = logging.getLogger(__name__)


def process_response(text):
    result_dict = set({})
    # first, split based on newlines to get individual entries
    entries = text.split()
    # now split the entries into key and value and insert them into the dict
    for entry in entries:
        _key, value = tuple(entry.split(":", maxsplit=1))
        result_dict.add(value)
    return result_dict


def test_count():
    # generate the filter code
    cmd = f"{COMPILER_BINARY} "
    cmd += f"-q {QUERY_DIR.joinpath('count.cql')} "
    cmd += f"-u {UDF_DIR.joinpath('count.cc')} "
    cmd += "-r productpage-v1 "
    result = util.exec_process(cmd)
    assert result == util.EXIT_SUCCESS
    # build the filter
    result = kube_env.build_filter(kube_env.FILTER_DIR)
    assert result == util.EXIT_SUCCESS
    # deploy the filter
    result = kube_env.refresh_filter(kube_env.FILTER_DIR)
    assert result == util.EXIT_SUCCESS
    # first, clean the storage
    storage_proc = storage.init_storage_mon()
    storage.query_storage("clean")

    # first request
    requests.send_request()
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "1" in result_set

    # second request
    requests.send_request()
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "2" in result_set

    # third request
    requests.send_request()
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "3" in result_set

    storage.kill_storage_mon(storage_proc)
    return util.EXIT_SUCCESS


def main(args):
    test_count()


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
