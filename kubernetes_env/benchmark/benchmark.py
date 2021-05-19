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
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import numpy as np
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


def transform_loadgen_data(filters, data):
    combined_data = {}
    for fname, loadgen in zip(filters, data):
        combined_data[fname] = loadgen
    return pd.DataFrame(combined_data, columns=filters)


def transform_fortio_data(filters):
    names = []
    json_data = []
    dfs = []
    title = ""
    for fname in filters:
        latency = [0]
        percentages = [0]
        with open(f"{DATA_DIR}/{fname}.json") as jsonf:
            hist_data = json.load(jsonf)["DurationHistogram"]
            fortio_data = hist_data["Data"]
            avg_ms = sec_to_ms(hist_data["Avg"])
            title += f"{fname} - avg: {avg_ms} ms. "
            for (idx, datum) in enumerate(fortio_data):
                if idx == 0:
                    latency.append(sec_to_ms(datum["Start"]))
                    percentages.append(datum["Percent"])
                latency.append(sec_to_ms(datum["End"]))
                percentages.append(datum["Percent"])
            df = pd.DataFrame({
                "Latency (ms)": latency,
                "Percent": percentages
            })
            dfs.append(df)
    return dfs, title


def plot(dfs, filters, title, fortio=True):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
    plot_name = "-".join(filters) + timestamp
    if fortio:
        for df in dfs:
            sns.lineplot(data=df, x="Latency (ms)", y="Percent")
        plt.legend(labels=filters)
        plt.title(f"Fortio: {title}")
    else:
        fig, (ax1,ax2) = plt.subplots(1,2, figsize=(18,6))
        dplot = sns.ecdfplot(dfs, ax= ax1)
        dplot.set(xlabel="Latency (ms)", ylabel="Percentiles")
        hplot = sns.histplot(dfs, ax= ax2)
        hplot.set(xlabel="Latency (ms)", ylabel="Count")     
    util.check_dir(GRAPHS_DIR)
    plt.savefig(f"{GRAPHS_DIR}/{plot_name}.png")
    log.info("Finished plotting. Check out the graphs directory!")
    return util.EXIT_SUCCESS


def run_fortio(url, platform, threads, qps, run_time, file_name):
    util.check_dir(DATA_DIR)
    output_file = str(DATA_DIR.joinpath(f"{file_name}.json"))
    fortio_dir = str(FORTIO_DIR)
    cmd = f"{fortio_dir} "
    cmd += f"load -c {threads} -qps {qps} -timeout 50s -t {run_time}s -json {output_file} "
    cmd += f"{url}"
    with open(output_file, "w") as f:
        fortio_res = util.exec_process(cmd,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        return fortio_res


def do_burst(url, platform, threads, qps, run_time):
    output = []

    def send_request(_):
        try:
            # What should timeout be?
            res = requests.get(url, timeout=3)
            ms = res.elapsed.total_seconds() * 1000
            return ms
        except requests.exceptions.Timeout:
            pass

    log.info("Starting burst...")

    with ThreadPoolExecutor(max_workers=threads) as p:
        current = datetime.now()
        end = current + timedelta(seconds=run_time)
        while current < end:
            results = list(
                p.map(send_request, range(qps)))
            current += timedelta(seconds=1)
            output += results
    return output


def start_benchmark(custom, filter_dirs, platform, threads, qps, run_time):
    if kube_env.check_kubernetes_status() != util.EXIT_SUCCESS:
        log.error("Kubernetes is not set up."
                  " Did you run the deployment script?")
        return util.EXIT_FAILURE

    _, _, gateway_url = kube_env.get_gateway_info(platform)
    product_url = f"http://{gateway_url}/productpage"
    log.info("Gateway URL: %s", product_url)
    results = []
    filters = []
    for f in DATA_DIR.glob("*"):
        if f.is_file():
            f.unlink()

    for (idx, fd) in enumerate(filter_dirs):
        build_res = kube_env.build_filter(fd)

        if build_res != util.EXIT_SUCCESS:
            log.error(
                "Building filter failed for %s."
                " Make sure you give the right path", fd)
            return util.EXIT_FAILURE

        filter_res = kube_env.refresh_filter(fd)
        if filter_res != util.EXIT_SUCCESS:
            log.error(
                "Deploying filter failed for %s."
                " Make sure you give the right path", fd)
            return util.EXIT_FAILURE

        # wait for kubernetes set up to finish
        time.sleep(180)
        fname = Path(fd).name
        filters.append(fname)
        log.info("Warming up...")
        for i in range(10):
            requests.get(product_url)
        if custom == "fortio":
            log.info("Running fortio...")
            fortio_res = run_fortio(product_url, platform, threads, qps,
                                    run_time, fname)
            if fortio_res != util.EXIT_SUCCESS:
                log.error("Error benchmarking for %s", fd)
                return util.EXIT_FAILURE
        else:
            log.info("Generating load...")
            burst_res = do_burst(product_url, platform, threads, qps, run_time)
            results.append(burst_res)

    if custom == "fortio":
        fortio_df, title = transform_fortio_data(filters)
        np.save("fortio", fortio_df)
        return plot(fortio_df, filters, title, fortio=True)
    else:
        loadgen_df = transform_loadgen_data(filters, results)
        np.save("output", loadgen_df)
        return plot(loadgen_df, filters, "", fortio=False)


def main(args):
    filter_dirs = args.filter_dirs
    threads = args.threads
    qps = args.qps
    platform = args.platform
    time = args.time
    custom = args.custom.lower()
    return start_benchmark(custom, filter_dirs, platform, threads, qps, time)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l",
                        "--log-file",
                        dest="log_file",
                        default="benchmark.log",
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
                        default=2,
                        help="Number of threads")
    parser.add_argument("-qps",
                        dest="qps",
                        type=int,
                        default=10,
                        help="Query per second")
    parser.add_argument("-t",
                        "--time",
                        dest="time",
                        type=int,
                        default=120,
                        help="Time for fortio")
    parser.add_argument("-cu",
                        "--use-custom",
                        dest="custom",
                        default="",
                        help="Running custom load generator.")
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
