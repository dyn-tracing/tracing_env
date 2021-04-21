#!/usr/bin/env python3
import argparse
import logging
import time
from pathlib import Path

import kubernetes_env.kube_util as util
import kubernetes_env.kube_env as kube_env
import kubernetes_env.send_request as requests
import kubernetes_env.query_storage as storage

# some folder definitions
FILE_DIR = Path.resolve(Path(__file__)).parent
COMPILER_DIR = FILE_DIR.joinpath("tracing_compiler")
COMPILER_BINARY = COMPILER_DIR.joinpath("target/debug/snicket")
QUERY_DIR = COMPILER_DIR.joinpath("example_queries")
UDF_DIR = COMPILER_DIR.joinpath("example_udfs")
AGGR_FILTER_DIR = COMPILER_DIR.joinpath("aggregation_filter_envoy");

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


def generate_filter(filter_name, udfs, distributed=False):
    log.info("Generating the filter %s with udfs %s", filter_name, udfs)
    cmd = f"{COMPILER_BINARY} "
    cmd += f"-q {QUERY_DIR.joinpath(filter_name)} "
    for udf in udfs:
        cmd += f"-u {UDF_DIR.joinpath(udf)} "
    cmd += "-r productpage-v1 "
    if distributed:
        cmd += f"-d "
        cmd += f"-o {kube_env.DISTRIBUTED_FILTER_DIR}/filter.rs "
    result = util.exec_process(cmd)
    return result


def bootstrap(distributed=False):
    # build the filter
    log.info("Building the filters")
    filter_dir = kube_env.FILTER_DIR
    if distributed:
        filter_dir = kube_env.DISTRIBUTED_FILTER_DIR

    result = kube_env.build_filter(filter_dir)
    assert result == util.EXIT_SUCCESS
    result = kube_env.build_filter(AGGR_FILTER_DIR)
    assert result == util.EXIT_SUCCESS
    log.info("Refresh the filters")
    result = kube_env.refresh_filter(filter_dir)
    result = kube_env.refresh_filter(AGGR_FILTER_DIR)
    # sleep a little, so things initialize better
    log.info("Sleeping for 60 seconds")
    time.sleep(60)
    # first, clean the storage
    log.info("Cleaning storage")
    storage_proc = storage.init_storage_mon()
    storage.query_storage("clean")
    return storage_proc


def test_count(platform="MK", distributed=False):
    # generate the filter code
    result = generate_filter("count.cql", ["count.cc"], distributed)
    assert result == util.EXIT_SUCCESS

    # bootstrap the filter
    storage_proc = bootstrap(distributed)

    # first request
    log.info("Sending request #1")
    requests.send_request(platform)
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "1" in result_set, "Expected 1 received %s" % result_set

    # second request
    log.info("Sending request #2")
    requests.send_request(platform)
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "2" in result_set, "Expected 2 received %s" % result_set

    # third request
    log.info("Sending request #3")
    requests.send_request(platform)
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "3" in result_set, "Expected 3 received %s" % result_set

    storage.kill_storage_mon(storage_proc)
    log.info("count test succeeded.")
    return util.EXIT_SUCCESS


def test_height(platform="MK", distributed=False):
    # generate the filter code
    result = generate_filter("height.cql", ["height.rs"], distributed)
    assert result == util.EXIT_SUCCESS

    # bootstrap the filter
    storage_proc = bootstrap(distributed)

    # first request
    log.info("Sending request #1")
    requests.send_request(platform)
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "2" in result_set, "expected 2 received %s" % result_set

    storage.kill_storage_mon(storage_proc)
    log.info("height test succeeded.")
    return util.EXIT_SUCCESS

def test_height_avg(platform="MK", distributed=False):
    # generate the filter code
    result = generate_filter("height.cql", ["height.rs", "avg.rs"], distributed)
    assert result == util.EXIT_SUCCESS

    # bootstrap the filter
    storage_proc = bootstrap(distributed)

    # first request
    log.info("Sending request #1")
    requests.send_request(platform)
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "3" in result_set, "expected 3 received %s" % result_set

    storage.kill_storage_mon(storage_proc)
    log.info("height test succeeded.")
    return util.EXIT_SUCCESS



def test_get_service_name(platform="MK", distributed=False):
    # generate the filter code
    result = generate_filter("get_service_name.cql", [], distributed)
    assert result == util.EXIT_SUCCESS

    # bootstrap the filter
    storage_proc = bootstrap(distributed)

    
    # first request
    log.info("Sending request #1")
    requests.send_request(platform)
    log.info("Querying storage")
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "productpage-v1" in result_set, (
        "Expected productpage-v1 received %s" % result_set)

    storage.kill_storage_mon(storage_proc)
    log.info("get_service_name test succeeded.")
    return util.EXIT_SUCCESS


def test_request_size(platform="MK", distributed=False):
    # generate the filter code
    result = generate_filter("request_size.cql", [], distributed)
    assert result == util.EXIT_SUCCESS

    # bootstrap the filter
    storage_proc = bootstrap(distributed)

    # first request
    log.info("Sending request #1")
    requests.send_request(platform)
    storage_content = storage.query_storage()
    text = storage_content.text
    result_set = process_response(text)
    assert "productpage-v1" in result_set, (
        "Expected productpage-v1 received %s" % result_set)

    storage.kill_storage_mon(storage_proc)
    log.info("request_size test succeeded.")
    return util.EXIT_SUCCESS


def main(args):
    # TODO: Commented queries are not working yet
    # UDF not implemented
    # test_count(args.platform)
    test_get_service_name(args.platform)
    #test_get_service_name(args.platform, True)
    test_height(args.platform)
    #test_height(args.platform, True)
    # Bug in serialization of data
    # test_request_size(args.platform)
    # test_height_avg(args.platform)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l",
                        "--log-file",
                        dest="log_file",
                        default="filter_test.log",
                        help="Specifies name of the log file.")
    parser.add_argument(
        "-ll",
        "--log-level",
        dest="log_level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"],
        help="The log level to choose.")
    parser.add_argument("-p",
                        "--platform",
                        dest="platform",
                        default="KB",
                        choices=["MK", "GCP"],
                        help="Which platform to run the scripts on."
                        "MK is minikube, GCP is Google Cloud Compute")
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
