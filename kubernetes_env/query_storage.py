#!/usr/bin/env python3
import signal
import os
import argparse
import logging
import requests
import kube_env
import kube_util as util
import time

log = logging.getLogger(__name__)

def launch_storage_mon():                                                       
    if kube_env.check_kubernetes_status() != util.EXIT_SUCCESS:                 
        log.error("Kubernetes is not set up."                                   
                  " Did you run the deployment script?")                        
        sys.exit(util.EXIT_FAILURE)                                             
    cmd = "kubectl get pods -lapp=storage-upstream "                            
    cmd += " -o jsonpath={.items[0].metadata.name} -n=storage"                  
    storage_pod_name = util.get_output_from_proc(cmd).decode("utf-8")           
    cmd = f"kubectl -n=storage port-forward {storage_pod_name} 8090:8080"       
    storage_proc = util.start_process(cmd, preexec_fn=os.setsid)                
    # Let settle things in a bit                                                
    time.sleep(2)                                                               
    return storage_proc

def init_storage_mon():
    util.kill_tcp_proc(8090)
    storage_proc = launch_storage_mon()
    return storage_proc


def query_storage(cmd="list"):
    storage_content = requests.get(f"http://localhost:8090/{cmd}")
    return storage_content


def kill_storage_mon(storage_proc):
    os.killpg(os.getpgid(storage_proc.pid), signal.SIGINT)


def main(args):
    storage_proc = init_storage_mon()
    ret = query_storage(args.cmd)
    if args.cmd == "list":
        log.info("Storage content:\n%s", ret.text)
    # kill the storage proc after the query
    kill_storage_mon(storage_proc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l",
                        "--log-file",
                        dest="log_file",
                        default="storage.log",
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
    parser.add_argument("-c",
                        "--cmd",
                        dest="cmd",
                        default="list",
                        choices=["clean", "list"],
                        help="The command to send to storage.")
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
