# Installation
Other than the installation for kubernetes and set up, you will need to run:

```
pip3 install seaborn locust
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
-cu	Custom load testing tools, currently support built-in loadgen, fortio and locust
-nf	If set, not benchmark with no filter
-o	Output graph file
-sp	Subpath to the application
-r	Request Type: GET, POST.
-a  Application to benchmark
-ar Custom arguments for fortio or locust
```

# To run built-in load generator
```
./benchmark.py -fds <PATH TO FILTER DIR>
```

# To run fortio with custom args:

**To add custom args provided by default for fortio, use -ar flag but ensure
it's at the end of the command**
```
./benchmark.py -fds <PATH TO FILTER DIR> -cu fortio -qps <QUERY PER SECONDS> -t <TIME>
-ar --content-type POST
```

# To run locust with custom args:

**To add custom args provided by default for locust, use -ar flag but ensure
it's at the end of the command**
```
./benchmark.py -fds <PATH TO FILTER DIR> -cu locust -a OB
-ar -u 10 -t 10s --headless
```



