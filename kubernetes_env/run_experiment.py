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
FILTER_DIR = FILE_DIR.joinpath("filters/filter_service_name")
NO_ISOMORPHISM_FILTER_DIR = FILE_DIR.joinpath("filters/filter_no_isomorphism")
NO_MERGE_FILTER_DIR = FILE_DIR.joinpath("filters/filter_no_merge")
EMPTY_FILTER_DIR = BENCHMARK_DIR.joinpath("rs-empty-filter") 

TOOLS_DIR = FILE_DIR.joinpath("tools")
PROJECT_ID = "dynamic-tracing"

QPS = 10
THREADS = 2
RUNTIME = 500

def application_experiment(platform, multizonal, application, empty_filter, arg_no_filter, filter_dirs):
    if application == "BK":
        bookinfo_experiment(platform, multizonal, empty_filter, arg_no_filter, filter_dirs)
    if application == "OB":
        online_boutique_experiment(platform, multizonal, empty_filter, arg_no_filter, filter_dirs)
    if application == "TT":
        if platform == "MK":
            log.error("Train ticket is not supported on minikube")
        elif platform == "GCP": 
            train_ticket_experiment(multizonal, empty_filter, arg_no_filter, filter_dirs)

def bookinfo_experiment(platform, multizonal, empty_filter, arg_no_filter, filter_dirs):
    filters = filter_dirs
    if arg_no_filter:
        filters = []
    no_filter = 'ON'
    if empty_filter:
        filters.append(EMPTY_FILTER_DIR)
    setup_application_deployment(platform, multizonal, "BK")
    output = platform + "bookinfo"
    start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= no_filter, subpath='productpage', request='GET', custom='')
    stop_kubernetes(platform)

def online_boutique_experiment(platform, multizonal, empty_filter, arg_no_filter, filter_dirs):
    filters = filter_dirs
    if arg_no_filter:
        filters = []
    no_filter = 'ON'
    if empty_filter:
        filters.append(EMPTY_FILTER_DIR)

    setup_application_deployment(platform, multizonal, "OB")
    output = platform + "online_boutique_index"
    start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
        output=output, no_filter=no_filter, subpath='', request='GET',
        custom='', plot_name = "Index - Online Boutique")
    stop_kubernetes(platform)
    #time.sleep(60)


    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_set_currency"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter= no_filter, subpath='setCurrency',
    #    request='CURRENCY', custom='', plot_name = "Set Currency - Online Boutique" )
    #stop_kubernetes(platform)
    #time.sleep(60)


    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_browse_product"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='product/6E92ZMYYFZ',
    #    request='GET', custom='', plot_name="Browse Product - Online Boutique")
    #stop_kubernetes(platform)

    #time.sleep(60)

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_view_cart"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='cart', request='GET',
    #    custom='', plot_name="View Cart - Online Boutique")
    #stop_kubernetes(platform)

    #time.sleep(60)

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_add_to_cart"
    #start_benchmark(filters, platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter=no_filter, subpath='cart',
    #    request='ADD_TO_CART', custom='', plot_name="Add to Cart - Online Boutique")
    #stop_kubernetes(platform)

    #time.sleep(60)

def train_ticket_experiment(multizonal, empty_filter, arg_no_filter, filter_dirs):
    filters = filter_dirs
    if arg_no_filter:
        filters = []
    no_filter = 'ON'
    if empty_filter:
        filters.append(EMPTY_FILTER_DIR)
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
        return application_experiment(args.platform,
                                      args.multizonal,
                                      args.application,
                                      args.empty_filter,
                                      args.no_filter,
                                      args.filter_dirs)
    else:
        bookinfo_experiment(args.platform,
                            args.multizonal,
                            args.empty_filter,
                            args.no_filter,
                            args.filter_dirs)
        online_boutique_experiment(args.platform,
                                   args.multizonal,
                                   args.empty_filter,
                                   args.no_filter,
                                   args.filter_dirs)
        train_ticket_experiment(args.multizonal,
                                args.emtpy_filter,
                                args.no_isomorphism_filter,
                                args.no_filter,
                                args.filter_dirs)


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
    parser.add_argument("-fds",
                    "--filter-dirs",
                    dest="filter_dirs",
                    nargs="*",
                    type=str,
                    default=[str(FILTER_DIR)],
                    help="List of directories of the filter")
    parser.add_argument("-nf",
                        "--no_filter",
                        dest="no_filter",
                        action="store_true",
                        help="Benchmark without using our system at all")
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
