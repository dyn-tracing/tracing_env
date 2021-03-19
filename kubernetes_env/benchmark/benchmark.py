#!/usr/bin/env python3
import argparse
import logging
import subprocess
import os
import sys
import signal
import requests
import time
import seaborn as sns
import pandas as pd
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
import json
from pathlib import Path

DIRS = Path(__file__).resolve().parents
sys.path.append(str(DIRS[1]))
import kube_env
import kube_util as util

log = logging.getLogger(__name__)
FILE_DIR = DIRS[0]
FILTER_DIR = FILE_DIR.joinpath("rs-empty-filter")
GRAPHS_DIR = FILE_DIR.joinpath("graphs")
DATA_DIR = FILE_DIR.joinpath("data")
FORTIO_DIR = DIRS[2].joinpath("bin/fortio")


def sec_to_ms(res_time):
    return round(float(res_time) * 1000, 3)


def convert_data(data):
    return {
        "Count":
        data["Count"],
        "Min":
        sec_to_ms(data["Min"]),
        "Max":
        sec_to_ms(data["Max"]),
        "Sum":
        sec_to_ms(data["Sum"]),
        "Avg":
        sec_to_ms(data["Avg"]),
        "StdDev":
        sec_to_ms(data["StdDev"]),
        "Data": [{
            "Start": sec_to_ms(datum["Start"]),
            "End": sec_to_ms(datum["End"]),
            "Percent": datum["Percent"],
            "Count": datum["Count"]
        } for datum in data["Data"]]
    }


def plot(files):
    fs = []
    log.info("Plotting...")
    names = []
    json_data = []
    for f in files:
        names.append(f.name.replace(".json", ""))
        with f.open() as jsonf:
            json_data.append(json.load(jsonf))
    if not json_data:
      log.error("No json data available")
      return util.EXIT_FAILURE
    converted_durations = [
        convert_data(data["DurationHistogram"]) for data in json_data
    ]
    dfs = []
    qps = json_data[0]["RequestedQPS"]
    duration = json_data[0]["RequestedDuration"]
    title = f"QPS: {qps}. Duration: ${duration}. "
    for (idx, converted_duration) in enumerate(converted_durations):
        res_times = [0]
        percentiles = [0]
        avg = converted_duration["Avg"]
        title += f"{names[idx]} Avg: {avg} ms. "
        for datum in converted_duration["Data"]:
            res_times.append(datum["Start"])
            res_times.append(datum["End"])
            percentiles.append(float(datum["Percent"]))
            percentiles.append(float(datum["Percent"]))
            d = {
                "Response time (ms)": res_times,
                "Percentiles": percentiles,
                "Filter": names[idx]
            }
            df = pd.DataFrame(data=d)
            dfs.append(df)
    final_df = pd.concat(dfs)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.lineplot(data=final_df,
                 x="Response time (ms)",
                 y="Percentiles",
                 hue="Filter",
                 ci=False,
                 marker='o')
    plt.title(title)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
    plot_name = "-".join(names) + timestamp
    util.check_dir(GRAPHS_DIR)
    plt.savefig(f"{GRAPHS_DIR}/{plot_name}.png")
    log.info("Finished plotting. Check out the graphs directory!")
    return util.EXIT_SUCCESS


def run_fortio(url, platform, threads, qps, run_time, file_name):
    util.check_dir(DATA_DIR)
    output_file = str(DATA_DIR.joinpath(f"{file_name}.json"))
    fortio_dir = str(FORTIO_DIR)
    cmd = f"{fortio_dir} "
    cmd += f"load -c {threads} -qps {qps} -jitter -t {run_time}s -json {output_file} "
    cmd += f"{url}"
    with open(output_file, "w") as f:
        fortio_res = util.exec_process(cmd,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        return fortio_res

def burst_loop(url, threads, qps, run_time):
    def send_request(_):
        try:
            start = round(time.time() * 1000)
            requests.get(url, timeout=0.5) 
            end = round(time.time() * 1000)
            return end - start
        except requests.exceptions.ReadTimeout:
            pass

    log.info("Starting burst...")

    results = None
    with ThreadPoolExecutor(max_workers=threads) as p:
        results = p.map(send_request, range(qps * run_time))
    log.info("Done with burst...")
    return results


def do_burst(url, platform, threads, qps, run_time):
    _, _, gateway_url = kube_env.get_gateway_info(platform)
    log.info(f"gateway url: {url}")
    p = Process(target=burst_loop, args=(url, threads, qps, run_time, ))
    p.start()

def start_benchmark(fortio, filter_dirs, platform, threads, qps, time):
    if kube_env.check_kubernetes_status() != util.EXIT_SUCCESS:
        log.error("Kubernetes is not set up."
                  " Did you run the deployment script?")
        return util.EXIT_FAILURE
    
    _, _, gateway_url = kube_env.get_gateway_info(platform)
    product_url = f"http://{gateway_url}/productpage"
    
    for f in DATA_DIR.glob("*"):
        if f.is_file():
            f.unlink()

    for (idx, fd) in enumerate(filter_dirs):
        build_res = kube_env.build_filter(fd)

        if build_res != util.EXIT_SUCCESS:
            log.error(f"Building filter failed for {fd}."
                      " Make sure you give the right path")
            return util.EXIT_FAILURE

        filter_res = kube_env.refresh_filter(fd)
        if filter_res != util.EXIT_SUCCESS:
            log.error(f"Deploying filter failed for {fd}."
                      " Make sure you give the right path")
            return util.EXIT_FAILURE

        log.info("Running fortio...")
        # Might break for filter_dir/
        fname = fd.split("/")[-1]
        # warm up with 100qps for 10s
        warmup_res = run_fortio(product_url, platform, threads, 100, 10, fname)
        if warmup_res != util.EXIT_SUCCESS:
            log.error(f"Error benchmarking for {fd}")
            return util.EXIT_FAILURE
        if fortio:
          fortio_res = run_fortio(product_url, platform, threads, qps, time, fname)
          if fortio_res != util.EXIT_SUCCESS:
              log.error(f"Error benchmarking for {fd}")
              return util.EXIT_FAILURE
        else:      
          results = do_burst(product_url, platform, threads, qps, time)
          for t in results:
            print(f"{t} ms")
    # dataf = [f for f in DATA_DIR.glob("*") if f.is_file()]
    # return plot(dataf)


def main(args):
    filter_dirs = args.filter_dirs
    threads = args.threads
    qps = args.qps
    platform = args.platform
    time = args.time
    fortio = args.fortio

    return start_benchmark(fortio, filter_dirs, platform, threads, qps, time)


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
    parser.add_argument("-fo",
                        "--fortio",
                        dest="fortio",
                        type=bool,
                        default=True,
                        help="Running fortio or not")
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
