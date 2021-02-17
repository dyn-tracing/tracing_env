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

def plot(xaxis_data, yaxis_data, xaxis_label, yaxis_label, graph_name = "graph") : 
    plt.plot(xaxis_data, yaxis_data, marker='o')
    plt.xlabel(xaxis_label)
    plt.ylabel(yaxis_label)
    if not check_dir("graph"):
      os.mkdir(os.path.join(FILE_DIR, "graphs"))
    plt.savefig(os.path.join(FILE_DIR, f"graphs/{graph_name}.png"))

def check_dir(dirname):
    return os.path.isdir(os.path.join(FILE_DIR, dirname))

def make_dir(dirname):
    os.mkdir(os.path.join(FILE_DIR, dirname))

def setup_filter(platform, multizonal):
    result = kube_env.setup_bookinfo_deployment(
         platform, multizonal)
    return result

def build_filter(filter_dir):
    result = kube_env.deploy_filter(filter_dir)
    return result

def teardown(platform):
    kube_env.stop_kubernetes(platform)

def run_fortio(platform, threads, qps, run_time):
    _, _, gateway_url = kube_env.get_gateway_info(platform)
    cmd = f"{FORTIO_DIR}/bin/fortio "
    cmd += f"load -c {threads} -qps {qps} -jitter -t {run_time}s -json data/output.json "
    cmd += f"http://{gateway_url}/productpage"
    fortio_proc = util.start_process(cmd, preexec_fn=os.setsid)
    outs, errs = fortio_proc.communicate()

def parse_output(file_name="data/output.json"):
    with open(file_name, "r") as f:
       fortio_json = f.load(f)
       actual_qps = fortio_json["ActualQPS"]
       actual_duration = fortio_json["ActualDuration"]
       print(f"Actual QPS: {actual_qps}. Actual duration: {actual_duration}")

def benchmark_lat(platform, threads, qps, time):
    run_fortio(platform, threads, qps, time)

def main(args):
    filter_dirs = args.filter_dirs
    threads = args.threads
    qps = args.qps
    latency = args.latency
    latency_gname = args.latency_gname
    platform = args.platform
    time = args.time
    
    if not check_dir("data"):
      make_dir("data")
    benchmark_lat(platform, threads, qps, time)
    parse_output()
    '''
    Build filters and tear down after each benchmark

    for filter_dir in filter_dirs:
      setup_res = setup_filter(args.platform, args.multizonal)
      if setup_res != util.EXIT_SUCCESS:
        return setup_res
      filter_res = build_filter(args.filter_dir)
      if filter_res != util.EXIT_SUCCESS:
        return filter_res

      # Start benchmarking
      if latency:
        benchmark_lat(t_requests, latency_gname, platform)
      
      teardown(args.platform)
    '''
    return util.EXIT_SUCCESS

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
                        default=kube_env.FILTER_DIR,
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
    parser.add_argument("-la", "--latency", dest="latency",
                        type=bool, default=True,
                        help="Measure latency or not?")
    parser.add_argument("-tp", "--throughput", dest="throughput",
                       type=bool, default=False,
                       help="Measure throughput or not?")
    parser.add_argument("--lat-gname", "--latency-graph-name",
                       dest="latency_gname", type=str,
                       default="latency-graph",
                       help="Name for latency graph")
    parser.add_argument("--tp-gname", "--throughput-graph-name",
                      dest="throughput_gname", type=str,
                      default="throughput-graph",
                      help="Name for throughput graph")

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
