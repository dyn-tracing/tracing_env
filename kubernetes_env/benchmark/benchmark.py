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

# Hotel Reservation(HR) is not supported as an application
APPLICATIONS = {
    "BK": "bookinfo_benchmark",
    "HR": "",
    "OB": "online_boutique_benchmark",
    "TT": "train_ticket_benchmark"
}


def sec_to_ms(res_time):
    return round(float(res_time) * 1000, 3)


def plot(dfs, filters, plot_name, custom):
    if custom == "locust":
        for df in dfs:
            sns.lineplot(data=df, x="Latency (ms)", y="Percent")
        plt.legend(labels=filters)
        plt.title(plot_name)
    elif custom == "fortio":
        for df in dfs:
            sns.lineplot(data=df, x="Latency (ms)", y="Percent")
        plt.legend(labels=filters)
        plt.title(plot_name)
    elif custom == "loadgen":
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 6))
        dplot = sns.ecdfplot(dfs, ax=ax1)
        dplot.set(xlabel="Latency (ms)", ylabel="Percentiles")
        dplot.set_title(plot_name)
        hplot = sns.histplot(dfs, ax=ax2)
        hplot.set(xlabel="Latency (ms)", ylabel="Count")
    else:
        log.info("No valid load generator supplied!")
        return util.EXIT_FAILURE

    util.check_dir(GRAPHS_DIR)
    plt.savefig(f"{GRAPHS_DIR}/{plot_name}.png")
    log.info("Finished plotting. Check out the graphs directory!")
    return util.EXIT_SUCCESS


def transform_locust_data(filters, application, path):
    dfs = []
    for fname in filters:
        csv_prefix = f"{application}"
        if fname != "no_filter":
          csv_prefix += f"_{fname}"
        csv_file_dir = str(FILE_DIR.joinpath(f"{csv_prefix}_stats.csv"))
        df = pd.read_csv(csv_file_dir)
        latency = []
        percentages = [50, 66, 75, 80, 90, 95, 98, 99, 100]
        path_df = df.loc[df["Name"] == f"/{path}"]
        for percentile in percentages:
            key = str(percentile)
            latency.append(path_df[f"{key}%"][0])
        dfs.append(
            pd.DataFrame({
                "Latency (ms)": latency,
                "Percent": percentages
            }))
    return dfs


def run_locust(url, platform, command_args, application, filename):
    py_file_dir = str(FILE_DIR.joinpath(f"{application}.py"))
    csv_prefix = f"{application}"
    if filename != "no_filter":
      csv_prefix += f"_{filename}"
    cmd = f"locust -f {py_file_dir} -H {url} {command_args} --csv {csv_prefix}"
    res = util.exec_process(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return res


def transform_fortio_data(filters):
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


def run_fortio(url, platform, threads, qps, run_time, command_args, filename):
    util.check_dir(DATA_DIR)
    output_file = str(DATA_DIR.joinpath(f"{filename}.json"))
    fortio_dir = str(FORTIO_DIR)
    cmd = f"{fortio_dir} load "
    cmd += f"-c {threads} -qps {qps} -timeout 50s -t {run_time}s -json {output_file} "
    cmd += " {command_args} "
    cmd += f"{url}"
    with open(output_file, "w") as f:
        res = util.exec_process(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        return res


def transform_loadgen_data(filters, data):
    combined_data = {}
    for fname, loadgen in zip(filters, data):
        combined_data[fname] = loadgen
    return pd.DataFrame(combined_data, columns=filters)


def run_loadgen(url, platform, threads, qps, run_time, request_type):
    output = []

    def get_request(_):
        try:
            # What should timeout be?
            res = requests.get(url, timeout=3)
            if res.status_code != 200:
                return None
            ms = res.elapsed.total_seconds() * 1000
            return ms
        except requests.exceptions.Timeout:
            pass

    def post_request(_):
        try:
            res = requests.post(url, timeout=3)
            if res.status_code != 200:
                return None
            ms = res.elapsed.total_seconds() * 1000
            return ms
        except requests.exceptions.Timeout:
            pass

    request_func = get_request if request_type == "GET" else post_request
    with ThreadPoolExecutor(max_workers=threads) as p:
        current = datetime.now()
        end = current + timedelta(seconds=run_time)
        while current < end:
            results = list(p.map(request_func, range(qps)))
            current += timedelta(seconds=1)
            output += [result for result in results if result]
    return output


def build_and_deploy_filter(filter_dir):
    res = kube_env.build_filter(filter_dir)

    if res != util.EXIT_SUCCESS:
        log.error(
            "Building filter failed for %s."
            " Make sure you give the right path", filter_dir)
        return util.EXIT_FAILURE

    res = kube_env.refresh_filter(filter_dir)
    if res != util.EXIT_SUCCESS:
        log.error(
            "Deploying filter failed for %s."
            " Make sure you give the right path", filter_dir)
        return util.EXIT_FAILURE

    # wait for kubernetes set up to finish
    time.sleep(120)
    return util.EXIT_SUCCESS


def start_benchmark(filter_dirs, platform, threads, qps, run_time, **kwargs):
    if kube_env.check_kubernetes_status() != util.EXIT_SUCCESS:
        log.error("Kubernetes is not set up."
                  " Did you run the deployment script?")
        return util.EXIT_FAILURE

    custom = kwargs.get("custom")
    request = kwargs.get("request")
    output = kwargs.get("output_file")
    command_args = " ".join(kwargs.get("command_args"))
    application = APPLICATIONS.get(kwargs.get("application"))

    _, _, gateway_url = kube_env.get_gateway_info(platform)
    path = kwargs.get("subpath")
    url = f"http://{gateway_url}/{path}"
    log.info("Gateway URL: %s", url)

    results = []
    filters = []

    if kwargs.get("no_filter") == "ON":
        filter_dirs.insert(0, "no_filter")
        filters.insert(0, "no_filter")

    for f in DATA_DIR.glob("*"):
        if f.is_file():
            f.unlink()

    for (idx, filter_dir) in enumerate(filter_dirs):
        log.info("Benchmarking %s", filter_dir)
        fname = Path(filter_dir).name
        if filter_dir != "no_filter":
            res = build_and_deploy_filter(filter_dir)
            if res != util.EXIT_SUCCESS:
                return util.EXIT_FAILURE
            filters.append(fname)

        log.info("Warming up...")
        for i in range(10):
            requests.get(url)

        if custom == "locust":
            if not application:
                log.error("Provided application does not exists")
                return util.EXIT_FAILURE
            log.info("Running locust...")
            res = run_locust(f"http://{gateway_url}", platform, command_args,
                             application, fname)
            if res != util.EXIT_SUCCESS:
                log.error("Error benchmarking %s application", application)
                return util.EXIT_FAILURE
        elif custom == "fortio":
            log.info("Running fortio...")
            fortio_res = run_fortio(url, platform, threads, qps, run_time,
                                    command_args, fname)
            if fortio_res != util.EXIT_SUCCESS:
                log.error("Error benchmarking for %s", fd)
                return util.EXIT_FAILURE
        elif custom == "loadgen":
            log.info("Generating load...")
            burst_res = run_loadgen(url, platform, threads, qps, run_time,
                                    request)
            results.append(burst_res)
        else:
            log.error("Invalid load generator")
            return util.EXIT_FAILURE

    # Plot functions
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    np_output = f"{custom} {application} {timestamp}"
    graph_output = f"{custom} {application} {timestamp}"
    if custom == "locust":
        locust_df = transform_locust_data(filters, application, path)
        np.save(np_output, locust_df)
        return plot(locust_df, filters, graph_output, custom)
    elif custom == "fortio":
        fortio_df, title = transform_fortio_data(filters)
        np.save(np_output, fortio_df)
        return plot(fortio_df, filters, graph_output, custom)
    elif custom == "loadgen":
        loadgen_df = transform_loadgen_data(filters, results)
        np.save(np_output, loadgen_df)
        return plot(loadgen_df, filters, graph_output, custom)


def main(args):
    return start_benchmark(args.filter_dirs,
                           args.platform,
                           args.threads,
                           args.qps,
                           args.time,
                           application=args.application,
                           no_filter=args.nf,
                           output_file=args.output_file,
                           subpath=args.subpath,
                           request=args.request,
                           command_args=args.command_args,
                           custom=args.custom.lower(),
                           plot_name=args.plot_name)


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
    parser.add_argument("-u",
                        "--users",
                        dest="users",
                        type=int,
                        default=10,
                        help="Number of users to spawn")
    parser.add_argument("-sr",
                        "--spawn-rate",
                        dest="spawn_rate",
                        type=int,
                        default=5,
                        help="Rate to spawn users")
    parser.add_argument("-qps",
                        "--query-per-second",
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
    parser.add_argument(
        "-a",
        "--application",
        dest="application",
        default="BK",
        choices=["BK", "HR", "OB", "TT"],
        help="Which application to deploy."
        "BK: bookinfo, HR: hotel reservation, OB: online boutique, TT: train ticket"
    )
    parser.add_argument("-cu",
                        "--use-custom",
                        dest="custom",
                        default="loadgen",
                        help="Running custom load generator.")
    parser.add_argument("-nf",
                        "--no-filter",
                        dest="nf",
                        default="ON",
                        help="Benchmark with no filter")
    parser.add_argument("-o",
                        "--output-file",
                        dest="output_file",
                        default="output",
                        help="Output data for the graph")
    parser.add_argument("-sp",
                        "--subpath",
                        dest="subpath",
                        default="productpage",
                        help="Path of the application")
    parser.add_argument("-r",
                        "--request",
                        dest="request",
                        default="GET",
                        help="Request type")
    parser.add_argument("-ar",
                        "--args",
                        dest="command_args",
                        default="",
                        nargs=argparse.REMAINDER,
                        help="Extra arguments for fortio or locust")
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
