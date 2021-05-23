#!/usr/bin/env python3
import argparse
import logging
import sys
import os
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

TOOLS_DIR = FILE_DIR.joinpath("tools")
PROJECT_ID = "dynamic-tracing"

QPS = 10
THREADS = 2
RUNTIME = 50

def application_experiment(platform, multizonal, application):
    if application == "BK":
        bookinfo_experiment(platform, multizonal)
    if application == "OB":
        online_boutique_experiment(platform, multizonal)
    if application == "TT":
        if platform == "MK":
            log.error("Train ticket is not supported on minikube")
        elif platform == "GCP": 
            train_ticket_experiment(multizonal)

def bookinfo_experiment(platform, multizonal):
    setup_application_deployment(platform, multizonal, "BK")
    output = platform + "bookinfo"
    start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= 'ON', subpath='productpage', request='GET', custom='')
    stop_kubernetes(platform)

def online_boutique_experiment(platform, multizonal):
    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_index"
    #start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter= 'ON', subpath='/', request='GET', custom='')
    #stop_kubernetes(platform)

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_set_currency"
    #start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter= 'ON', subpath='setCurrency', request='CURRENCY', custom='')
    #stop_kubernetes(platform)

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_browse_product"
    #start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter= 'ON', subpath='/product/6E92ZMYYFZ', request='GET', custom='')
    #stop_kubernetes(platform)

    #setup_application_deployment(platform, multizonal, "OB")
    #output = platform + "online_boutique_view_cart"
    #start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
    #    output=output, no_filter= 'ON', subpath='/cart', request='GET', custom='')
    #stop_kubernetes(platform)

    setup_application_deployment(platform, multizonal, "OB")
    output = platform + "online_boutique_add_to_cart"
    start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= 'ON', subpath='/cart', request='ADD_TO_CART', custom='')
    stop_kubernetes(platform)

    setup_application_deployment(platform, multizonal, "OB")
    output = platform + "online_boutique_checkout"
    start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= 'ON', subpath='/cart', request='CHECKOUT', custom='')
    stop_kubernetes(platform)

def train_ticket_experiment(multizonal):
    setup_application_deployment('GCP', multizonal, 'TT')

    output = platform + "train_ticket_home"
    start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= 'ON', subpath='/index.html', request='GET', custom='')

    output = platform + "train_ticket_client_login"
    start_benchmark([FILTER_DIR], platform, THREADS, QPS, RUNTIME,
        output=output, no_filter= 'ON', subpath='/client_login.html', request='GET', custom='')
    
    stop_kubernetes('GCP')

def main(args):
    # single commands to execute
    if args.application:
        return application_experiment(args.platform, args.multizonal, args.application)
    else:
        bookinfo_experiment(args.platform, args.multizonal)
        online_boutique_experiment(args.platform, args.multizonal)
        #train_ticket_experiment(args.platform, args.multizonal)


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
