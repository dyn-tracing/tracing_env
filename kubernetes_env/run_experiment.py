#!/usr/bin/env python3
import argparse
import logging
import sys
import os
import time
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from kube_env import setup_application_deployment, stop_kubernetes
from benchmark.benchmark import start_benchmark
import requests

import kube_util as util

log = logging.getLogger(__name__)

FILE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = FILE_DIR.parent
BENCHMARK_DIR = FILE_DIR.joinpath("benchmark")
COMPILER_DIR = FILE_DIR.joinpath("tracing_compiler")
FILTER_DIR = FILE_DIR.joinpath("filter_service_name")
NO_ISOMORPHISM_FILTER_DIR = FILE_DIR.joinpath("filter_no_isomorphism")
EMPTY_FILTER_DIR = BENCHMARK_DIR.joinpath("rs-empty-filter") 

TOOLS_DIR = FILE_DIR.joinpath("tools")
PROJECT_ID = "dynamic-tracing"

QPS = 10
THREADS = 2
RUNTIME = 50

def application_experiment(platform, multizonal, application, empty_filter, no_isomorphism_filter):
    if application == "BK":
        bookinfo_experiment(platform, multizonal, empty_filter, no_isomorphism_filter)
    if application == "OB":
        online_boutique_experiment(platform, multizonal, empty_filter, no_isomorphism_filter)
    if application == "TT":
        if platform == "MK":
            log.error("Train ticket is not supported on minikube")
        elif platform == "GCP": 
            train_ticket_experiment(multizonal, empty_filter, no_isomorphism_filter)

def bookinfo_experiment(platform, multizonal, empty_filter, no_isomorphism_filter):
    filters = [FILTER_DIR]
    no_filter = 'ON'
    if empty_filter:
        filters.append(EMPTY_FILTER_DIR)
        no_filter = 'OFF'
    if no_isomorphism_filter:
        filters.append(NO_ISOMORPHISM_FILTER_DIR)
        no_filter = 'OFF'
    setup_application_deployment(platform, multizonal, "BK")
    output = platform + "bookinfo"
    start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= no_filter, subpath='productpage', request='GET', custom='')
    stop_kubernetes(platform)

def online_boutique_experiment(platform, multizonal, empty_filter, no_isomorphism_filter):
    filters = [FILTER_DIR]
    no_filter = 'ON'
    if empty_filter:
        filters.append(EMPTY_FILTER_DIR)
        no_filter = 'OFF'
    if no_isomorphism_filter:
        filters.append(NO_ISOMORPHISM_FILTER_DIR)
        no_filter = 'OFF'

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_index"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='/', request='GET', custom='')
    #time.sleep(60)
    #stop_kubernetes(platform)


    setup_application_deployment(platform, multizonal, "OB")
    output = platform + "online_boutique_set_currency"
    start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= no_filter, subpath='setCurrency', request='CURRENCY', custom='')
    time.sleep(60)
    stop_kubernetes(platform)


    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_browse_product"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='product/6E92ZMYYFZ', request='GET', custom='')
    #stop_kubernetes(platform)

    #time.sleep(60)

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_view_cart"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='cart', request='GET', custom='')
    #stop_kubernetes(platform)

    #time.sleep(60)

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_add_to_cart"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='cart', request='ADD_TO_CART', custom='')
    #time.sleep(60)
    #stop_kubernetes(platform)

    #time.sleep(60)

    # TODO: This one doesn't work currently - might be somethign wrong with the url?
    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_checkout"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='cart', request='CHECKOUT', custom='')
    #time.sleep(60)
    #stop_kubernetes(platform)

def train_ticket_experiment(multizonal, empty_filter, no_isomorphism_filter):
    filters = [FILTER_DIR]
    no_filter = 'ON'
    if empty_filter:
        filters.append(EMPTY_FILTER_DIR)
        no_filter = 'OFF'
    if no_isomorphism_filter:
        filters.append(NO_ISOMORPHISM_FILTER_DIR)
        no_filter = 'OFF'


    #setup_application_deployment('GCP', multizonal, 'TT')
    output = "GCPtrain_ticket_home"
    start_benchmark(filters, 'GCP', THREADS, QPS, RUNTIME,
        output=output, no_filter= no_filter, subpath='index.html', request='GET', custom='')
    time.sleep(60)
    stop_kubernetes('GCP')

    #setup_application_deployment('GCP', multizonal, 'TT')
    #output = platform + "train_ticket_client_login"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter= no_filter, subpath='client_login.html', request='GET', custom='')
    #time.sleep(60)
    #stop_kubernetes('GCP')

def main(args):
    # single commands to execute
    if args.application:
        return application_experiment(args.platform, args.multizonal, args.application, args.empty_filter, args.no_isomorphism_filter)
    else:
        bookinfo_experiment(args.platform, args.multizonal, args.empty_filter, args.no_isomorphism_filter)
        online_boutique_experiment(args.platform, args.multizonal, args.empty_filter, args.no_isomorphism_filter)
        #train_ticket_experiment(args.platform, args.multizonal, args.emtpy_filter, args.no_isomorphism_filter)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l",
                        "--log-file",
                        dest="log_file",
                        default="model.log",
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
                        default="MK",
                        choices=["MK", "GCP"],
                        help="Which platform to run the scripts on."
                        "MK is minikube, GCP is Google Cloud Compute")
    parser.add_argument("-e",
                        "--empty_filter",
                        dest="empty_filter",
                        action="store_true",
                        help="Add empty filter to compare against")
    parser.add_argument("-i",
                        "--no_isomorphism_filter",
                        dest="no_isomorphism_filter",
                        action="store_true",
                        help="Add no isomorphism filter to compare against")
    parser.add_argument("-a",
                        "--application",
                        dest="application",
                        choices=["BK", "OB", "TT"],
                        help="Which application to deploy."
                        "BK is bookinfo, HR is hotel reservation, and OB is online boutique")
    parser.add_argument("-m",
                        "--multi-zonal",
                        dest="multizonal",
                        action="store_true",
                        help="If you are running on GCP,"
                        " do you want a multi-zone cluster?")
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
    sys.exit(main(arguments))
