#!/usr/bin/env python3
import argparse
import logging
import sys
import os
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

import kube_util as util

log = logging.getLogger(__name__)

FILE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = FILE_DIR.parent
ISTIO_DIR = FILE_DIR.joinpath("istio-1.9.3")
ISTIO_BIN = ISTIO_DIR.joinpath("bin/istioctl")
YAML_DIR = FILE_DIR.joinpath("yaml_crds")
TOOLS_DIR = FILE_DIR.joinpath("tools")
ONLINE_BOUTIQUE_DIR = FILE_DIR.joinpath("microservices-demo")
HOTEL_RESERVATION_DIR = FILE_DIR.joinpath("DeathStarBench/hotelReservation")
TRAIN_TICKET_DIR = FILE_DIR.joinpath("train-ticket/deployment/kubernetes-manifests/k8s-with-istio")
PROJECT_ID = "dynamic-tracing"
APPLY_CMD = "kubectl apply -f "
DELETE_CMD = "kubectl delete -f "
CONFIG_MATRIX = {
    'BK': {
        'minikube_startup_command': "minikube start --cpus=2 --memory 4096 --disk-size 32g",
        'gcloud_startup_command':"gcloud container clusters create demo --enable-autoupgrade \
                                  --enable-autoscaling --min-nodes=3 \
                                  --max-nodes=10 --num-nodes=5 ",
        'deploy_cmd': f"{APPLY_CMD} {YAML_DIR}/bookinfo-services.yaml && \
                        {APPLY_CMD} {YAML_DIR}/bookinfo-apps.yaml && \
                        {APPLY_CMD} {ISTIO_DIR}/samples/bookinfo/networking/bookinfo-gateway.yaml && \
                        {APPLY_CMD} {ISTIO_DIR}/samples/bookinfo/networking/destination-rule-reviews.yaml ",
        'undeploy_cmd': f"{ISTIO_DIR}/samples/bookinfo/platform/kube/cleanup.sh" 
    },
    'OB': {
        'minikube_startup_command': "minikube start --cpus=4 --memory 4096 --disk-size 32g",
        'gcloud_startup_command':"gcloud container clusters create demo --enable-autoupgrade \
                                  --enable-autoscaling --min-nodes=3 \
                                  --max-nodes=10 --num-nodes=5 ",
        'deploy_cmd': f"{APPLY_CMD} {ONLINE_BOUTIQUE_DIR}/release ",
        'undeploy_cmd': f"{DELETE_CMD} {ONLINE_BOUTIQUE_DIR}/release "
    },
    'HR': {
        'minikube_startup_command': None,
        'gcloud_startup_command':"gcloud container clusters create demo --enable-autoupgrade \
                                  --enable-autoscaling --min-nodes=3 \
                                  --max-nodes=10 --num-nodes=7 ",
        'deploy_cmd': f"{APPLY_CMD} {HOTEL_RESERVATION_DIR}/kubernetes ",
        'undeploy_cmd': f"{DELETE_CMD} {HOTEL_RESERVATION_DIR}/kubernetes ",
    },
    'TT': {
        'minikube_startup_command': None,
        'gcloud_startup_command':"gcloud container clusters create demo --enable-autoupgrade \
                                  --enable-autoscaling --min-nodes=3 \
                                  --max-nodes=15 --num-nodes=8 ",
        'deploy_cmd': f"{ISTIO_BIN} kube-inject -f {TRAIN_TICKET_DIR}/ts-deployment-part1.yml > dpl1.yml && " +
                      f"{APPLY_CMD} dpl1.yml && " +
                      f"{ISTIO_BIN} kube-inject -f {TRAIN_TICKET_DIR}/ts-deployment-part2.yml > dpl2.yml && " +
                      f"{APPLY_CMD} dpl2.yml && " +
                      f"{ISTIO_BIN} kube-inject -f {TRAIN_TICKET_DIR}/ts-deployment-part3.yml > dpl3.yml && " +
                      f"{APPLY_CMD} dpl3.yml && " +
                      f"{APPLY_CMD} {TRAIN_TICKET_DIR}/trainticket-gateway.yaml && " +
                      " rm dpl1.yml dpl2.yml dpl3.yml ",
        'undeploy_cmd': f"{DELETE_CMD} {TRAIN_TICKET_DIR}/ts-deployment-part1.yml && " +
                      f"{DELETE_CMD} {TRAIN_TICKET_DIR}/ts-deployment-part2.yml && " +
                      f"{DELETE_CMD} {TRAIN_TICKET_DIR}/ts-deployment-part3.yml "
    },
}


FILTER_DIR = FILE_DIR.joinpath("../tracing_compiler/filter_envoy")
DISTRIBUTED_FILTER_DIR = FILE_DIR.joinpath(
    "../tracing_compiler/distributed_filter_envoy")
CM_FILTER_NAME = "rs-filter"
# the kubernetes python API sucks, but keep this for later

# from kubernetes import client
# from kubernetes.client.configuration import Configuration
# from kubernetes.utils import create_from_yaml
# from kubernetes.config import kube_config
# def get_e2e_configuration():
#     config = Configuration()
#     config.host = None
#     kube_config.load_kube_config(client_configuration=config)
#     log.info('Running test against : %s' % config.host)
#     return config
# conf = get_e2e_configuration()
# k8s_client = client.api_client.ApiClient(configuration=conf)
# create_from_yaml(k8s_client, f"{bookinfo_dir}/platform/kube/bookinfo.yaml")



############## PLATFORM RELATED FUNCTIONS ###############################
def inject_istio():
    cmd = f"{ISTIO_BIN} install --set profile=demo "
    cmd += "--set meshConfig.enableTracing=true --skip-confirmation "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result
    cmd = "kubectl label namespace default istio-injection=enabled --overwrite"
    result = util.exec_process(cmd)

    cmd = f"{ISTIO_BIN} install --set profile=demo -n storage "
    cmd += "--set meshConfig.enableTracing=true --skip-confirmation "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result
    cmd = "kubectl label namespace storage istio-injection=enabled --overwrite"
    result = util.exec_process(cmd)

    return result


def deploy_addons(addons):
    apply_cmd = "kubectl apply -f "
    url = "https://raw.githubusercontent.com/istio/istio/release-1.9"
    cmd = ""
    if "kiali" in addons:
        addons.append("kiali")
    for (idx, addon) in enumerate(addons):
        if addon == "prometheus-mod":
            cmd += f"{apply_cmd} {YAML_DIR}/prometheus-mod.yaml"
        else:
            cmd += f"{apply_cmd} {url}/samples/addons/{addon}.yaml"
        if idx < len(addons) - 1:
            cmd += " && "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result

    cmd = "kubectl get deploy -n istio-system -o name --all-namespaces "
    deployments = util.get_output_from_proc(cmd).decode("utf-8").strip()
    deployments = deployments.split("\n")
    for depl in deployments:
        wait_cmd = "kubectl rollout status -n istio-system "
        wait_cmd += f"{depl} -w --timeout=180s"
        _ = util.exec_process(wait_cmd)
    log.info("Addons are ready.")
    return util.EXIT_SUCCESS


def remove_addons(addons):
    remove_cmd = "kubectl delete -f"
    url = "https://raw.githubusercontent.com/istio/istio/release-1.9"
    cmd = ""
    for (idx, addon) in enumerate(addons):
        if addon == "prometheus-mod":
            cmd += f"{remove_cmd} {YAML_DIR}/prometheus-mod.yaml --ignore-not-found=true"
        else:
            cmd += f"{remove_cmd} {url}/samples/addons/{addon}.yaml --ignore-not-found=true"
        if idx < len(addons) - 1:
            cmd += " && "
    return util.exec_process(cmd)


def application_wait():
    cmd = "kubectl get deploy -o name"
    deployments = util.get_output_from_proc(cmd).decode("utf-8").strip()
    deployments = deployments.split("\n")
    for depl in deployments:
        wait_cmd = f"kubectl rollout status {depl} -w --timeout=180s"
        _ = util.exec_process(wait_cmd)
    log.info("Application is ready.")
    return util.EXIT_SUCCESS

def inject_failure():
    cmd = f"kubectl apply -f {YAML_DIR}/fault-injection.yaml "
    result = util.exec_process(cmd)
    return result


def remove_failure():
    cmd = f"kubectl delete -f {YAML_DIR}/fault-injection.yaml "
    result = util.exec_process(cmd)
    return result


def check_kubernetes_status():
    cmd = "kubectl cluster-info"
    result = util.exec_process(cmd,
                               stdout=util.subprocess.PIPE,
                               stderr=util.subprocess.PIPE)
    return result


def start_kubernetes(platform, multizonal, application):
    if platform == "GCP":
        # 1. Create cluster enabled with Istio already
        cmd = CONFIG_MATRIX[application]['gcloud_startup_command']
        if multizonal:
            cmd += "--region us-central1-a --node-locations us-central1-b "
            cmd += "us-central1-c us-central1-a "
        else:
            cmd += "--zone=us-central1-a "
        result = util.exec_process(cmd)
        cmd = f"gcloud services enable container.googleapis.com --project {PROJECT_ID} &&"
        cmd += f"gcloud services enable monitoring.googleapis.com cloudtrace.googleapis.com "
        cmd += f"clouddebugger.googleapis.com cloudprofiler.googleapis.com --project {PROJECT_ID}"
        result = util.exec_process(cmd)
        if result != util.EXIT_SUCCESS:
            return result

        # 2. Create storage namespace
        cmd = "kubectl create namespace storage"
        result = util.exec_process(cmd)
        if result != util.EXIT_SUCCESS:
            return result

    else:
        # 1. Create cluster
        if CONFIG_MATRIX[application]['minikube_startup_command'] != None:
            cmd = CONFIG_MATRIX[application]['minikube_startup_command']
            result = util.exec_process(cmd)
            if result != util.EXIT_SUCCESS:
                return result
        else:
            return "APPLICATION IS NOT SUPPORTED ON MINIKUBE"

        # 2. Create storage namespace
        cmd = "kubectl create namespace storage"
        result = util.exec_process(cmd)
        if result != util.EXIT_SUCCESS:
            return result

    return result


def stop_kubernetes(platform):
    if platform == "GCP":
        cmd = "gcloud container clusters delete "
        cmd += "demo --zone us-central1-a --quiet "
    else:
        # delete minikube
        cmd = "minikube delete"
    result = util.exec_process(cmd)
    return result


def get_gateway_info(platform):
    ingress_host = ""
    ingress_port = ""
    if platform == "GCP":
        cmd = "kubectl -n istio-system get service istio-ingressgateway "
        cmd += "-o jsonpath={.status.loadBalancer.ingress[0].ip} "
        ingress_host = util.get_output_from_proc(cmd).decode("utf-8").replace(
            "'", "")

        cmd = "kubectl -n istio-system get service istio-ingressgateway "
        cmd += " -o jsonpath={.spec.ports[?(@.name==\"http2\")].port}"
        ingress_port = util.get_output_from_proc(cmd).decode("utf-8").replace(
            "'", "")
    else:
        cmd = "minikube ip"
        ingress_host = util.get_output_from_proc(cmd).decode("utf-8").rstrip()
        cmd = "kubectl -n istio-system get service istio-ingressgateway"
        cmd += " -o jsonpath={.spec.ports[?(@.name==\"http2\")].nodePort}"
        ingress_port = util.get_output_from_proc(cmd).decode("utf-8")

    log.debug("Ingress Host: %s", ingress_host)
    log.debug("Ingress Port: %s", ingress_port)
    gateway_url = f"{ingress_host}:{ingress_port}"
    log.debug("Gateway: %s", gateway_url)

    return ingress_host, ingress_port, gateway_url


def burst_loop(url):
    NUM_REQUESTS = 500
    MAX_THREADS = 32

    def timeout_request(_):
        try:
            # the timeout effectively makes this request async
            requests.get(url, timeout=0.001)
        except requests.exceptions.ReadTimeout:
            pass

    log.info("Starting burst...")
    # quick hack until I found a better way
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as p:
        for _ in p.map(timeout_request, range(NUM_REQUESTS)):
            pass
    log.info("Done with burst...")


def do_burst(platform):
    _, _, gateway_url = get_gateway_info(platform)
    url = f"http://{gateway_url}/productpage"
    p = Process(target=burst_loop, args=(url, ))
    p.start()
    # do not care about killing that process


def start_fortio(gateway_url):
    cmd = f"{FILE_DIR}/bin/fortio "
    cmd += "load -c 50 -qps 300 -jitter -t 0 -loglevel Warning "
    cmd += f"http://{gateway_url}/productpage"
    fortio_proc = util.start_process(cmd, preexec_fn=os.setsid)
    return fortio_proc


############### FILTER RELATED FUNCTIONS ######################################
def build_filter(filter_dir):
    # TODO: Move this into a script in the filter dir
    log.info("Building filter...")
    cmd = "cargo +nightly build -Z unstable-options "
    cmd += "--target=wasm32-unknown-unknown --release "
    cmd += f"--out-dir {filter_dir}/wasm_bins "
    cmd += f"--target-dir {filter_dir}/target "
    cmd += f"--manifest-path {filter_dir}/Cargo.toml "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result
    # Also build the aggregation filter
    cmd = "cargo +nightly build -Z unstable-options "
    cmd += "--target=wasm32-unknown-unknown --release "
    cmd += f"--out-dir {filter_dir}/wasm_bins "
    cmd += f"--target-dir {filter_dir}/target "
    cmd += f"--manifest-path {filter_dir}/agg/Cargo.toml "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result
    log.info("Build successful!")
    return result


def undeploy_filter():
    # delete the config map
    delete_config_map()
    cmd = f"kubectl delete -f {YAML_DIR}/filter.yaml "
    result = util.exec_process(cmd, allow_failures=True)
    if result != util.EXIT_SUCCESS:
        log.warning("Failed to delete the filter.")
    # restore the original bookinfo
    return deploy_bookinfo()

def patch_application():
    cmd = "kubectl get deploy -o name"
    deployments = util.get_output_from_proc(cmd).decode("utf-8").strip()
    deployments = deployments.split("\n")
    for depl in deployments:
        patch_cmd = f"kubectl patch {depl} "
        patch_cmd += f"--patch-file {YAML_DIR}/cm_patch.yaml "
        result = util.exec_process(patch_cmd)
        if result != util.EXIT_SUCCESS:
            log.error("Failed to patch %s.", depl)
    # we also patch storage
    patch_cmd = "kubectl patch -n storage deployment.apps/storage-upstream "
    patch_cmd += f"--patch-file {YAML_DIR}/cm_patch.yaml "
    result = util.exec_process(patch_cmd)
    if result != util.EXIT_SUCCESS:
        log.error("Failed to patch storage.")
    return result


def create_conf_map(filter_dir):
    cmd = f"kubectl create configmap {CM_FILTER_NAME} "
    cmd += f"--from-file {filter_dir}/wasm_bins/filter.wasm "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        log.error("Failed to create config map.")
        return result

    # also refresh the aggregation filter
    cmd = f"kubectl -n storage create configmap {CM_FILTER_NAME} "
    cmd += f"--from-file {filter_dir}/wasm_bins/agg_filter.wasm "
    return util.exec_process(cmd)


def delete_config_map():
    cmd = f"kubectl delete configmap {CM_FILTER_NAME} "
    result = util.exec_process(cmd, allow_failures=True)
    if result != util.EXIT_SUCCESS:
        log.warning("Failed to delete the config map, it does not exist.")
    # repeat this process for stage
    cmd = f"kubectl delete -n storage configmap {CM_FILTER_NAME} "
    return util.exec_process(cmd, allow_failures=True)


def update_conf_map(filter_dir):
    # delete the config map
    result = delete_config_map()
    if result != util.EXIT_SUCCESS:
        log.warning("Assuming a patch is required.")
        result = create_conf_map(filter_dir)
        if result != util.EXIT_SUCCESS:
            return result
        # update the containers with the config map
        return patch_application()
    # "refresh" the filter by recreating the config map
    return create_conf_map(filter_dir)


def deploy_filter(filter_dir):
    # check if the config map already exists
    # we assume that if the config map does not exist in default
    # it also does not exist in storage
    cmd = f"kubectl get configmaps {CM_FILTER_NAME} "
    result = util.exec_process(cmd, allow_failures=True)
    if result == util.EXIT_SUCCESS:
        # Config map exists, assume that the deployment is already modded
        log.warning("Config map %s already exists!", CM_FILTER_NAME)
        # delete and recreate the config map
        return update_conf_map(filter_dir)
    # create the config map with the filter
    result = create_conf_map(filter_dir)
    if result != util.EXIT_SUCCESS:
        return result
    # update the containers with the config map
    result = patch_application()
    if result != util.EXIT_SUCCESS:
        return result
    # now activate the filter
    cmd = f"kubectl apply -f {YAML_DIR}/filter.yaml"
    return util.exec_process(cmd)


def refresh_filter(filter_dir):

    # delete and recreate the config map
    update_conf_map(filter_dir)

    # activate the filter
    cmd = f"kubectl apply -f {YAML_DIR}/filter.yaml"
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result
    # this is equivalent to a deployment restart right now
    cmd = "kubectl rollout restart  deployments --namespace=default"
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result

    # also reset storage since we are working with a different filter now
    cmd = "kubectl rollout restart deployment storage-upstream -n=storage "
    result = util.exec_process(cmd)
    if result != util.EXIT_SUCCESS:
        return result
    return application_wait()


def handle_filter(args):
    if args.build_filter:
        return build_filter(args.filter_dir)
    if args.deploy_filter:
        return deploy_filter(args.filter_dir)
    if args.undeploy_filter:
        return undeploy_filter()
    if args.refresh_filter:
        return refresh_filter(args.filter_dir)
    log.warning("No command line input provided. Doing nothing.")
    return util.EXIT_SUCCESS


################### APPLICATION SPECIFIC FUNCTIONS ###########################

def deploy_application(application):
    if check_kubernetes_status() != util.EXIT_SUCCESS:
        log.error("Kubernetes is not set up."
                  " Did you run the deployment script?")
        sys.exit(util.EXIT_FAILURE)
    cmd = CONFIG_MATRIX[application]['deploy_cmd']
    cmd += f" && {APPLY_CMD} {YAML_DIR}/storage.yaml && "
    cmd += f"{APPLY_CMD} {YAML_DIR}/istio-config.yaml && "
    cmd += f"{APPLY_CMD} {YAML_DIR}/root-cluster.yaml "
    result = util.exec_process(cmd)
    application_wait()
    return result

def remove_application(application):
    cmd = CONFIG_MATRIX[application]['undeploy_cmd']
    cmd += f" && {DELETE_CMD} {YAML_DIR}/storage.yaml && "
    cmd += f"{DELETE_CMD} {YAML_DIR}/root-cluster.yaml "
    result = util.exec_process(cmd)
    return result

def setup_application_deployment(platform, multizonal, application):
    result = start_kubernetes(platform, multizonal, application)
    if result != util.EXIT_SUCCESS:
        return result
    result = inject_istio()
    if result != util.EXIT_SUCCESS:
        return result
    result = deploy_application(application)
    if result != util.EXIT_SUCCESS:
        return result
    return result

def main(args):
    # single commands to execute
    if args.setup:
        return setup_application_deployment(args.platform, args.multizonal, args.application)
    if args.deploy_application:
        return deploy_application(args.application)
    if args.remove_application:
        return remove_application(args.application)
    if args.deploy_addons:
        return deploy_addons(args.deploy_addons)
    if args.remove_addons:
        return remove_addons(args.remove_addons)
    if args.clean:
        return stop_kubernetes(args.platform)
    if args.burst:
        return do_burst(args.platform)
    return handle_filter(args)


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
                        default="KB",
                        choices=["MK", "GCP"],
                        help="Which platform to run the scripts on."
                        "MK is minikube, GCP is Google Cloud Compute")
    parser.add_argument("-a",
                        "--application",
                        dest="application",
                        default="BK",
                        choices=["BK", "HR", "OB", "TT"],
                        help="Which platform to run the scripts on."
                        "BK is bookinfo, HR is hotel reservation, and OB is online boutique")
    parser.add_argument("-m",
                        "--multi-zonal",
                        dest="multizonal",
                        action="store_true",
                        help="If you are running on GCP,"
                        " do you want a multi-zone cluster?")
    parser.add_argument("-s",
                        "--setup",
                        dest="setup",
                        action="store_true",
                        help="Just do a deployment. "
                        "This means installing the application and Kubernetes."
                        " Do not run any experiments.")
    parser.add_argument("-c",
                        "--clean",
                        dest="clean",
                        action="store_true",
                        help="Clean up an existing deployment. ")
    parser.add_argument("-fd",
                        "--filter-dir",
                        dest="filter_dir",
                        default=FILTER_DIR,
                        help="The directory of the filter")
    parser.add_argument("-db",
                        "--deploy-application",
                        dest="deploy_application",
                        action="store_true",
                        help="Deploy the app. ")
    parser.add_argument("-rb",
                        "--remove-application",
                        dest="remove_application",
                        action="store_true",
                        help="remove the app. ")
    parser.add_argument("-bf",
                        "--build-filter",
                        dest="build_filter",
                        action="store_true",
                        help="Build the WASM filter. ")
    parser.add_argument("-df",
                        "--deploy-filter",
                        dest="deploy_filter",
                        action="store_true",
                        help="Deploy the WASM filter. ")
    parser.add_argument("-uf",
                        "--undeploy-filter",
                        dest="undeploy_filter",
                        action="store_true",
                        help="Remove the WASM filter. ")
    parser.add_argument("-rf",
                        "--refresh-filter",
                        dest="refresh_filter",
                        action="store_true",
                        help="Refresh the WASM filter. ")
    parser.add_argument("-b",
                        "--burst",
                        dest="burst",
                        action="store_true",
                        help="Burst with HTTP requests to cause"
                        " congestion and queue buildup.")
    parser.add_argument("-da",
                        "--deploy-addons",
                        dest="deploy_addons",
                        nargs="+",
                        type=str,
                        default=[],
                        help="Deploy addons. ")
    parser.add_argument("-ra",
                        "--remove-addons",
                        dest="remove_addons",
                        nargs="+",
                        type=str,
                        default=[],
                        help="Remove addons. ")
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
