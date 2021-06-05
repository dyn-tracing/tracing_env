#!/usr/bin/env python3
import seaborn as sns
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pathlib
import pathlib
import kube_env
import kube_util as util

def graph(title, csv_path, output):
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


    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 6))

    cols = []
    for col in df.columns:
        if col != "Time":
            cols.append(col)
            df[col] = df[col].replace("undefined", "nan")
            df[col] = df[col].astype(float, errors='ignore')*1000 # change to milliseconds
            dplt = sns.lineplot(data=df, x="Time", y=col, ax=ax1)
            dplt.legend(labels=cols, bbox_to_anchor=(0.65, -0.2), loc='upper left', ncol=2, mode="expand", prop={'size': 6})
            dplt.set(ylabel = "Milliseconds of CPU time used per second")
            dplt.set_title("CPU Usage By Container")

    df["cpu_all"] = df[cols].sum(axis=1)
    df["cpu_all"] = df["cpu_all"].replace("undefined", "nan")
    df["cpu_all"] = df["cpu_all"].astype(float, errors='ignore')*1000 # change to milliseconds
    hplt = sns.lineplot(data=df, x="Time", y="cpu_all", ax=ax2)
    hplt.set(ylabel="Milliseconds of CPU time used per second")
    hplt.set_title("CPU Usage Of All Containers")

    plt.subplots_adjust(bottom=0.6, right=1)
    print("Saving to: ", output)
    plt.savefig(output)

def main(args):
    return graph(args.title, args.source, args.output)

if __name__ == '__main__':                                                      
    path = pathlib.Path().absolute()
    parser = argparse.ArgumentParser()                                          
    parser.add_argument("-t",  
                        "--title",                                           
                        dest="title",                                        
                        default="CPU Usage By Container",                                
                        help="Specifies title of graph.")  
    parser.add_argument("-s",  
                        "--source",                                           
                        dest="source",                                        
                        default=f"{path}/Kubernetes_Container_-_CPU_usage_time_[RATE].csv",  
                        help="Specifies source of data.")  
    parser.add_argument("-o",  
                        "--output",                                           
                        dest="output", 
                        default="cpu_plot.png",  
                        help="Specifies where graph is saved.")  
    arguments = parser.parse_args()
    main(arguments)
