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


def generate_filter(filter_name, udfs):
    log.info("Generating the filter %s with udfs %s", filter_name, udfs)
    cmd = f"{COMPILER_BINARY} "
    cmd += f"-q {QUERY_DIR.joinpath(filter_name)} "
    for udf in udfs:
        cmd += f"-u {UDF_DIR.joinpath(udf)} "
    cmd += "-r productpage-v1 "
    result = util.exec_process(cmd)
    return result


def bootstrap():
    # build the filter
    log.info("Building the filter")
    result = kube_env.build_filter(kube_env.FILTER_DIR)
    assert result == util.EXIT_SUCCESS
    log.info("Refresh the filter")
    result = kube_env.refresh_filter(kube_env.FILTER_DIR)
    # sleep a little, so things initialize better
    log.info("Sleeping for 10 seconds")
    time.sleep(20)
    # first, clean the storage
    log.info("Cleaning storage")
    storage_proc = storage.init_storage_mon()
    storage.query_storage("clean")
    return storage_proc


def test_get_service_name(platform="MK"):
    # generate the filter code
    result = generate_filter("get_service_name.cql", [])
    assert result == util.EXIT_SUCCESS

    # bootstrap the filter
    storage_proc = bootstrap()

    found_reviews_3 = False
    request_num = 1;
    result_set = None
    while not found_reviews_3:
        log.info("Sending request %d" % request_num);
        request_num += 1
        response = requests.send_request(platform).headers

        response_fd = response['ferried_data']

        if "reviews-v3" in response_fd:
            found_reviews_3 = True
        storage_content = storage.query_storage()
        text = storage_content.text
        result_set = process_response(text)
        if request_num == 30:
            found_reviews_3 = True # don't want to loop forever - depend on assertion for correctness
    assert("productpage-v1" in result_set, "received %s" % result_set)

    storage.kill_storage_mon(storage_proc)
    log.info("get service name test succeeded.")
    return util.EXIT_SUCCESS


def test_return_height(platform="MK"):
    # generate the filter code
    result = generate_filter("height.cql", ["height.rs"])
    assert result == util.EXIT_SUCCESS

    # bootstrap the filter
    storage_proc = bootstrap()

    # send requests
    found_reviews_1 = False
    request_num = 1;
    result_set = None
    while not found_reviews_1:
        log.info("Sending request %d" % request_num);
        request_num += 1
        response = requests.send_request(platform).headers

        response_fd = response['ferried_data']

        if "reviews-v1" in response_fd:
            found_reviews_1 = True
        storage_content = storage.query_storage()
        text = storage_content.text
        result_set = process_response(text)
        if request_num == 30:
            found_reviews_1 = True # don't want to loop forever - depend on assertion for correctness

    assert "2" in result_set, "expected 2 received %s" % result_set

    storage.kill_storage_mon(storage_proc)
    log.info("height test succeeded.")
    return util.EXIT_SUCCESS

def main(args):
    test_get_service_name(args.platform)
    test_return_height(args.platform)


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
