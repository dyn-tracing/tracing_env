#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import requests
import time
import matplotlib.pyplot as plt

sys.path.append("..")
import kube_env

log = logging.getLogger(__name__)
mypath = os.path.abspath(os.path.dirname(__file__))


"""
    Check if the response code is a successful request
    The function takes:
       - response: a response object
"""
def is_successful(response):
    return response.status_code == 200

def check_dir():
    return os.path.isdir(os.path.join(mypath, "graphs"))

def send_request(args):
    _, _, gateway_url = kube_env.get_gateway_info(args.platform)
    url = f"http://{gateway_url}/productpage"
    response = requests.get(url)
    return response

"""
    Iterating over total numbers of request and measure the
    latency in seconds
"""
def send_requests(numb_request, args):
    latency_ls = []
    for i in range(numb_request):
      start = time.time() 
      res = send_request(args)
      if(is_successful(res)):
        latency = time.time() - start
        latency_ls.append(latency)
      else:
        log.error(res.headers)
    return latency_ls

"""
    Get average latency and convert to float with 1 decimal 
"""
def get_ave_latency(args):
    ave_latency = []
    numb_requests = args.latency
    for numb_request in numb_requests:
       print(f"Getting latency for {numb_request} requests")
       latency_ls = send_requests(numb_request, args)
       ave_latency.append(sum(latency_ls) / len(latency_ls))
    ave_latency = [float("{:.1f}".format(latency)) for latency in ave_latency]
    return ave_latency

"""
    General purpose plot function and save to graphs dir
"""
def plot(xaxis_data, yaxis_data, xaxis_label, yaxis_label, graph_name = "graph") : 
    plt.plot(xaxis_data, yaxis_data, marker='o')
    plt.xlabel(xaxis_label)
    plt.ylabel(yaxis_label)
    if not check_dir():
      os.mkdir(os.path.join(mypath, "graphs"))
    plt.savefig(os.path.join(mypath, f"graphs/{graph_name}.png"))
       

def main(args):
    if args.latency:
      ave_latency = get_ave_latency(args)
      plot(args.latency, ave_latency, "Number of requests", "Latency (s)", args.latency_gname) 

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
    parser.add_argument("-lat", "--latency", dest="latency",
                        nargs="+", type=int, default="1000",
                        help="Number of requests to measure latency")
    parser.add_argument("-tp", "--throughput", dest="throughput",
                       nargs="+", type=int, default="1000",
                       help="Number of requests to measure throughput")
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
