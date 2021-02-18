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


def plot(xaxis_data, yaxis_data, xaxis_label, yaxis_label, query, graph_name):
    plt.plot(xaxis_data, yaxis_data, marker='o')
    plt.xlabel(xaxis_label)
    plt.ylabel(yaxis_label)
    plt.title(query)
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
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      return fortio_res

def get_histogram(file_name):
    with open(f"data/{file_name}", "r") as f:
       fortio_json = json.load(f)
       data = fortio_json["DurationHistogram"]
       return data

def benchmark_filter(platform, threads, qps, time, file_name, graph_name):
    fortio_res = run_fortio(platform, threads, qps, time)
    if fortio_res == util.EXIT_FAILURE:
      return fortio_res
    data = get_histogram(file_name)
    if data is not None:
      latency_data = data["Data"]
      response_times = [resp["End"] - resp["Start"] for resp in latency_data]
      request_counts = [resp["Count"] for resp in latency_data]
      plot(response_times, request_counts, "Response time (ms)", 
           "Requests", f"Platform: {platform} Threads: {threads} QPS: {qps}", graph_name)
      return util.EXIT_SUCCESS
    else:
      log.error("Error in processing data")
      return util.EXIT_FAILURE

def start_benchmark(filter_dirs, platform, 
                    threads, qps, time, file_name, graph_name):
    if kube_env.check_kubernetes_status() != util.EXIT_SUCCESS:
      log.error("Kubernetes is not set up."
                  " Did you run the deployment script?")
      return util.EXIT_FAILURE

    for (idx, filter_dir) in enumerate(filter_dirs):
      build_res = kube_env.build_filter(filter_dir)

      if build_res != util.EXIT_SUCCESS:
        log.error(f"Setting filter failed for {filter_dir}." 
                    " Make sure you give the right path")
        return util.EXIT_FAILURE

      filter_res = kube_env.deploy_filter(filter_dir) 
      if filter_res != util.EXIT_SUCCESS:
        log.error(f"Setting filter failed for {filter_dir}." 
                    " Make sure you give the right path")
        return util.EXIT_FAILURE
      
      benchmark_res = benchmark_filter(platform, threads, qps, time,
                       file_name, f"{graph_name}{idx}")
      if benchmark_res != util.EXIT_SUCCESS:
        log.error(f"Error benchmarking for {filter_dir}")
        return util.EXIT_FAILURE

      undeploy_res = kube_env.undeploy_filter()
      if undeploy_res != util.EXIT_SUCCESS:
        log.error(f"Setting filter failed for {filter_dir}." 
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

    return start_benchmark(filter_dirs, platform, threads,
                    qps, time, file_name, graph_name)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log-file", dest="log_file",
                        default="benchmark.log",
                        help="Spe:cifies name of the log file.")
    parser.add_argument("-ll", "--log-level", dest="log_level",
                        default="INFO",
                        choices=["CRITICAL", "ERROR", "WARNING",
                                 "INFO", "DEBUG", "NOTSET"],
                        help="The log level to choose.")
    parser.add_argument("-p", "--platform", dest="platform",
                        default="KB",
                        choices=["MK", "GCP"],
                        help="Which platform to run the scripts on."
                        "MK is minikube, GCP is Google Cloud Compute")
    parser.add_argument("-m", "--multi-zonal", dest="multizonal",
                        action="store_true",
                        help="If you are running on GCP,"
                        " do you want a multi-zone cluster?")                      
    parser.add_argument("-fds", "--filter-dirs", dest="filter_dirs",
                        nargs="+", type=str,
                        default=[str(FILTER_DIR)],
                        help="List of directories of the filter")
    parser.add_argument("-th", "--threads", dest="threads",
                        type=int, default=50,
                        help="Number of threads")
    parser.add_argument("-qps", dest="qps",
                        type=int, default=300,
                        help="Query per second")
    parser.add_argument("-t", "--time", dest="time",
                        type=int, default=5,
                        help="Time for fortio")
    parser.add_argument("-fname", "--file-name", dest="file_name",
                        type=str, default="output.json",
                        help="JSON file for fortio to write to")
    parser.add_argument("-gname", "--graph-name", dest="graph_name",
                        type=str, default="benchmark",
                        help="Graph file to output to")

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
