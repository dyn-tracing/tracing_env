#!/usr/bin/env python3
import argparse
import logging
import subprocess
import os
import sys
import signal
import requests
import time
import matplotlib.pyplot as plt
import json
from pathlib import Path

DIRS = Path(__file__).resolve().parents
sys.path.append(str(DIRS[1]))
import kube_env
import kube_util as util

log = logging.getLogger(__name__)
FILE_DIR = DIRS[0]
FILTER_DIR = FILE_DIR.joinpath("cpp_filter")
GRAPHS_DIR = FILE_DIR.joinpath("graphs")
DATA_DIR = FILE_DIR.joinpath("data")
FORTIO_DIR = DIRS[2].joinpath("bin/fortio")


def plot(x, y, x_label, y_label, query, graph_name, **general_info):
    extra_info = ". ".join(f"{k}: {v:.4f}" for k, v in general_info.items())
    plt.title(f"{query}.\n{extra_info}", fontsize='small')
    plt.plot(x, y, marker='o')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    util.check_dir(GRAPHS_DIR)
    plt.savefig(str(GRAPHS_DIR.joinpath(f"{graph_name}.png")))


def run_fortio(platform, threads, qps, run_time):
    util.check_dir(DATA_DIR)
    _, _, gateway_url = kube_env.get_gateway_info(platform)
    output_file = str(DATA_DIR.joinpath("output.json"))
    fortio_dir = str(FORTIO_DIR)
    cmd = f"{fortio_dir} "
    cmd += f"load -c {threads} -qps {qps} -jitter -t {run_time}s -json {output_file} "
    cmd += f"http://{gateway_url}/productpage"
    with open(output_file, "w") as f:
        fortio_res = util.exec_process(cmd,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        return fortio_res


def get_data(file_name):
    with open(f"data/{file_name}", "r") as f:
        fortio_json = json.load(f)
        return fortio_json


def benchmark_filter(platform, threads, qps, time, file_name, graph_name):
    fortio_res = run_fortio(platform, threads, qps, time)
    if fortio_res == util.EXIT_FAILURE:
        return fortio_res
    data = get_data(file_name)
    if data is not None:
        histogram_data = data["DurationHistogram"]
        latency = histogram_data["Data"]
        response_times = [resp["End"] - resp["Start"] for resp in latency]
        request_counts = [resp["Count"] for resp in latency]
        plot(response_times,
             request_counts,
             "Response time (ms)",
             "Count",
             f"Platform: {platform}. Threads: {threads}. QPS: {qps}",
             graph_name,
             count=histogram_data["Count"],
             min_val=histogram_data["Min"],
             max_val=histogram_data["Max"],
             average=histogram_data["Avg"],
             std=histogram_data["StdDev"])
        return util.EXIT_SUCCESS
    else:
        log.error("Error in processing data")
        return util.EXIT_FAILURE


def start_benchmark(fortio, filter_dirs, platform, threads, qps, time,
                    file_name, graph_name):
    if kube_env.check_kubernetes_status() != util.EXIT_SUCCESS:
        log.error("Kubernetes is not set up."
                  " Did you run the deployment script?")
        return util.EXIT_FAILURE

    for (idx, filter_dir) in enumerate(filter_dirs):
        build_res = kube_env.build_filter(filter_dir)

        if build_res != util.EXIT_SUCCESS:
            log.error(f"Building filter failed for {filter_dir}."
                      " Make sure you give the right path")
            return util.EXIT_FAILURE

        filter_res = kube_env.deploy_filter(filter_dir)
        if filter_res != util.EXIT_SUCCESS:
            log.error(f"Deploying filter failed for {filter_dir}."
                      " Make sure you give the right path")
            return util.EXIT_FAILURE

        benchmark_res = benchmark_filter(platform, threads, qps, time, file_name,
                                       f"{graph_name}{idx}")
        if benchmark_res != util.EXIT_SUCCESS:
            log.error(f"Error benchmarking for {filter_dir}")
            return util.EXIT_FAILURE

        undeploy_res = kube_env.undeploy_filter()
        if undeploy_res != util.EXIT_SUCCESS:
            log.error(f"Undeploy filter failed for {filter_dir}."
                      " Make sure you give the right path")
            return util.EXIT_FAILURE
    return util.EXIT_SUCCESS


def main(args):
    filter_dirs = args.filter_dirs
    threads = args.threads
    qps = args.qps
    platform = args.platform
    time = args.time
    file_name = args.file_name
    graph_name = args.graph_name
    fortio = args.fortio

    if args.gateway:
        _, _, gateway_url = kube_env.get_gateway_info(platform)
        print(gateway_url)
    elif args.log_app:
        app = args.log_app
        proxy = args.proxy
        cmd = "kubectl logs "
        cmd += f"`(kubectl get pods -lapp={app}" 
        cmd += " -o jsonpath={.items[0].metadata.name})` "
        if proxy:
            cmd += "istio-proxy"
        else:
            cmd += app

        res = util.exec_process(cmd)
        if res == 0:
            log.info("Success")
        else:
            log.info("Something wrong happened")
    else:
        return start_benchmark(fortio, filter_dirs, platform, threads, qps,
                               time, file_name, graph_name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l",
                        "--log-file",
                        dest="log_file",
                        default="benchmark.log",
                        help="Spe:cifies name of the log file.")
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
    parser.add_argument("-m",
                        "--multi-zonal",
                        dest="multizonal",
                        action="store_true",
                        help="If you are running on GCP,"
                        " do you want a multi-zone cluster?")
    parser.add_argument("-fds",
                        "--filter-dirs",
                        dest="filter_dirs",
                        nargs="+",
                        type=str,
                        default=[str(FILTER_DIR)],
                        help="List of directories of the filter")
    parser.add_argument("-th",
                        "--threads",
                        dest="threads",
                        type=int,
                        default=4,
                        help="Number of threads")
    parser.add_argument("-qps",
                        dest="qps",
                        type=int,
                        default=300,
                        help="Query per second")
    parser.add_argument("-t",
                        "--time",
                        dest="time",
                        type=int,
                        default=5,
                        help="Time for fortio")
    parser.add_argument("-fname",
                        "--file-name",
                        dest="file_name",
                        type=str,
                        default="output.json",
                        help="JSON file for fortio to write to")
    parser.add_argument("-gname",
                        "--graph-name",
                        dest="graph_name",
                        type=str,
                        default="benchmark",
                        help="Graph file to output to")
    parser.add_argument("-fo",
                        "--fortio",
                        dest="fortio",
                        type=bool,
                        help="Running fortio or not")

    parser.add_argument("-gw",
                        "--gateway",
                        dest="gateway",
                        type=bool,
                        help="Printing out gateway")
    parser.add_argument("-la",
                        "--lapp",
                        dest="log_app",
                        type=str,
                        help="App to log")
    parser.add_argument("-px",
                        "--proxy",
                        dest="proxy",
                        type=bool,
                        help="Log proxy or not")


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
