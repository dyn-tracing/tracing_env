start up a minikube cluster, this might take a while

`./kubernetes_env/kube_env.py --setup`

build the skeleton filter we have generated

`./kubernetes_env/kube_env.py --build-filter --filter-dir kubernetes_env/benchmark/cpp_filter`

deploy this filter, this might take a little

`./kubernetes_env/kube_env.py --deploy-filter --filter-dir kubernetes_env/benchmark/cpp_filter`

send a request

`./kubernetes_env/send_request.py`


# Installation
Other than the installation for kubernetes and set up, you will need to run:

```
pip3 install seaborn pandas
```
