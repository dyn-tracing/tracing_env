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

sys.path.append("..")

import kube_env
import kube_util as util

log = logging.getLogger(__name__)
FILE_DIR = os.path.abspath(os.path.dirname(__file__))
# Haven't found a workaround
FORTIO_DIR = Path(__file__).parent.resolve().parent.resolve().parent.resolve()

def plot(xaxis_data, yaxis_data, xaxis_label, yaxis_label, query, graph_name):
    plt.plot(xaxis_data, yaxis_data, marker='o')
    plt.xlabel(xaxis_label)
    plt.ylabel(yaxis_label)
    plt.title(query)
    if not check_dir("graphs"):
      os.mkdir(os.path.join(FILE_DIR, "graphs"))
    plt.savefig(os.path.join(FILE_DIR, f"graphs/{graph_name}.png"))

def check_dir(dirname):
    return os.path.isdir(os.path.join(FILE_DIR, dirname))

def make_dir(dirname):
    os.mkdir(os.path.join(FILE_DIR, dirname))

def run_fortio(platform, threads, qps, run_time):
    if not check_dir("data"):
      make_dir("data")
    _, _, gateway_url = kube_env.get_gateway_info(platform)
    cmd = f"{FORTIO_DIR}/bin/fortio "
    cmd += f"load -c {threads} -qps {qps} -jitter -t {run_time}s -json data/output.json "
    cmd += f"http://{gateway_url}/productpage"
    fortio_proc = util.start_process(cmd, preexec_fn=os.setsid)
    outs, errs = fortio_proc.communicate()

def get_histogram(file_name):
    with open(f"data/{file_name}", "r") as f:
       fortio_json = json.load(f)
       data = fortio_json["DurationHistogram"]
       return data

def benchmark_filter(platform, threads, qps, time, file_name, graph_name):
    run_fortio(platform, threads, qps, time)
    data = get_histogram(file_name)
    if data is not None:
      latency_data = data["Data"]
      response_times = [resp["End"] - resp["Start"] for resp in latency_data]
      request_counts = [resp["Count"] for resp in latency_data]
      plot(response_times, request_counts, "Response time (ms)", 
           "Requests", f"Platform: {platform} Threads: {threads} QPS: {qps}", graph_name)
    else:
      log.error("Error in processing data")

def start_benchmark(filter_dirs, platform, 
                    threads, qps, time, file_name, graph_name):
    if kube_env.check_kubernetes_status() != util.EXIT_SUCCESS:
      log.error("Kubernetes is not set up."
                  " Did you run the deployment script?")
      sys.exit(util.EXIT_FAILURE)

    # Undeploy current running filter
    kube_env.undeploy_filter() 
    for (idx, filter_dir) in enumerate(filter_dirs):
      build_res = kube_env.build_filter(filter_dir)

      if build_res != util.EXIT_SUCCESS:
        log.error(f"Setting filter failed for {filter_dir}." 
                    " Make sure you give the right path")
        sys.exit(util.EXIT_FAILURE)

      filter_res = kube_env.deploy_filter(filter_dir) 
      if filter_res != util.EXIT_SUCCESS:
        log.error(f"Setting filter failed for {filter_dir}." 
                    " Make sure you give the right path")
        sys.exit(util.EXIT_FAILURE)
      
      benchmark_filter(platform, threads, qps, time,
                       file_name, f"{graph_name}{idx}")
      undeploy_res = kube_env.undeploy_filter()
      if undeploy_res != util.EXIT_SUCCESS:
        log.error(f"Setting filter failed for {filter_dir}." 
                    " Make sure you give the right path")
        sys.exit(util.EXIT_FAILURE)
      


def main(args):
    filter_dirs = args.filter_dirs
    threads = args.threads
    qps = args.qps
    platform = args.platform
    time = args.time
    file_name = args.file_name
    graph_name = args.graph_name

    start_benchmark(filter_dirs, platform, threads,
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
                        default="./cpp_filter",
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
