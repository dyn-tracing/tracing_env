# Installation
Other than the installation for kubernetes and set up, you will need to run:

```
pip3 install seaborn pandas
```

# Usage
Start up a minikube cluster, this might take a while

`./kubernetes_env/kube_env.py --setup`

Run benchmark script:

`./benchmark.py -fds <PATH TO FILTER DIR>`

Flag details:


```
-fds	Path to filter directories. Can be multiple
-qps	Query to send per seconds
-t	Duration for benchmarking
-th	Number of threads to use	
-cu	Custom load testing tools, currently support fortio
-nf	If set, not benchmark with no filter
-o	Output graph file
-sp	Subpath to the application
-r	Request Type: GET, POST.
```



