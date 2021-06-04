#!/usr/bin/env python3
import seaborn as sns
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pathlib
import pathlib
import kube_env
import kube_util as util

path = pathlib.Path().absolute()
csv_path = f"{path}/Kubernetes_Container_-_CPU_usage_time_[RATE].csv"
old_to_new_names = {}
df = pd.read_csv(csv_path)
for col in df.columns:
    if col != "Time":
        start_pod_name = col.find("pod_name")
        start_pod = col[start_pod_name:].find(":")+start_pod_name+1
        end_pod = col[start_pod:].find(".")
        pod_name = col[start_pod:start_pod+end_pod]

        start_container_name = col.find("container_name")
        start_container = col[start_container_name:].find(":")+start_container_name+1
        end_container = col[start_container:].find(".")
        container_name = col[start_container: start_container+end_container]

        new_column_name = pod_name + "_" + container_name
        old_to_new_names[col] = new_column_name

df.rename(columns=old_to_new_names, inplace=True)
df["Time"] = df["Time"].str[3:]
df["Time"] = df["Time"].str[:21]
df["Time"] = pd.to_datetime(df["Time"], infer_datetime_format=True)

cols = []
for col in df.columns:
    if col != "Time":
        cols.append(col)
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')*1000 # change to milliseconds
        sns.lineplot(data=df, x="Time", y=col)
plt.subplots_adjust(right=0.7)
plt.legend(labels=cols, bbox_to_anchor=(1.04, 0.5), loc='center left', ncol=1, mode="expand", prop={'size': 2})
plt.ylabel("Milliseconds of CPU time used per second")
plt.title("CPU Usage By Container")
plt.show()


