#!/usr/bin/env python3
import seaborn as sns
import argparse
import numpy as np
import pandas as pd
from numpy import median
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

    # get different columns
    app_cols = df.columns[df.columns.str.contains('_server|_storage-upstream')]
    istio_cols = df.columns[df.columns.str.contains('istio-proxy')]
    fluentbit_cols = df.columns[df.columns.str.contains('fluentbit')]
    gke_cols = df.columns[df.columns.str.contains('gke-metrics')]
    kube_cols = df.columns[df.columns.str.contains('kube-dns|kube-proxy')]
    pdcsi_cols = df.columns[df.columns.str.contains('pdcsi')]
    time_col = df.columns[df.columns == 'Time']
    other_cols = df.columns[~df.columns.isin(app_cols|istio_cols|fluentbit_cols|gke_cols|kube_cols|pdcsi_cols|time_col)]
    assert df.columns.shape[0] == app_cols.shape[0] + istio_cols.shape[0] + fluentbit_cols.shape[0] + gke_cols.shape[0] + kube_cols.shape[0] + pdcsi_cols.shape[0] + other_cols.shape[0] + 1

    subtitle_fontsize = 12

    # app
    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.7)


    for col in app_cols:
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')
        dplt = sns.lineplot(data=df, x="Time", y=col)
        dplt.legend(labels=app_cols, bbox_to_anchor=(1.01, 1.01), loc='upper left', ncol=1, mode="expand", prop={'size': 8})
        dplt.set(ylabel = "Seconds of CPU time used per second")
        dplt.set_title("CPU Usage By Application Container", fontsize=subtitle_fontsize)
        axes = plt.gca()
        axes.set_ylim([0,0.1])

    print("Saving to: ", f"{output}_app.png")
    plt.savefig(f"{output}_app.png")
    plt.clf()
    plt.cla()

    # istio
    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.7)

    for col in istio_cols:
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')
        dplt = sns.lineplot(data=df, x="Time", y=col)
        dplt.legend(labels=app_cols, bbox_to_anchor=(1.01, 1.01), loc='upper left', ncol=1, mode="expand", prop={'size': 8})
        dplt.set(ylabel = "Seconds of CPU time used per second")
        dplt.set_title("CPU Usage By Istio Container", fontsize=subtitle_fontsize)

        axes = plt.gca()
        axes.set_ylim([0,0.1])

    print("Saving to: ", f"{output}_istio.png")
    plt.savefig(f"{output}_istio.png")
    plt.clf()
    plt.cla()

    # fluentbit
    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.7)

    for col in fluentbit_cols:
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')
        dplt = sns.lineplot(data=df, x="Time", y=col)
        dplt.legend(labels=fluentbit_cols, bbox_to_anchor=(1.01, 1.01), loc='upper left', ncol=1, mode="expand", prop={'size': 8})
        dplt.set(ylabel = "Seconds of CPU time used per second")
        dplt.set_title("CPU Usage By Fluentbit Container", fontsize=subtitle_fontsize)
        axes = plt.gca()
        axes.set_ylim([0,0.1])

    print("Saving to: ", f"{output}_fluentbit.png")
    plt.savefig(f"{output}_fluentbit.png")
    plt.clf()
    plt.cla()

    # kube
    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.7)

    for col in kube_cols:
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')
        dplt = sns.lineplot(data=df, x="Time", y=col)
        dplt.legend(labels=kube_cols, bbox_to_anchor=(1.01, 1.01), loc='upper left', ncol=1, mode="expand", prop={'size': 8})
        dplt.set(ylabel = "Seconds of CPU time used per second")
        dplt.set_title("CPU Usage By Kubernetes Container", fontsize=subtitle_fontsize)
        axes = plt.gca()
        axes.set_ylim([0,0.1])

    print("Saving to: ", f"{output}_kube.png")
    plt.savefig(f"{output}_kube.png")
    plt.clf()
    plt.cla()


    # gke
    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.7)

    for col in gke_cols:
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')
        dplt = sns.lineplot(data=df, x="Time", y=col)
        dplt.legend(labels=gke_cols, bbox_to_anchor=(1.01, 1.01), loc='upper left', ncol=1, mode="expand", prop={'size': 8})
        dplt.set(ylabel = "Seconds of CPU time used per second")
        dplt.set_title("CPU Usage By GKE Metrics Container", fontsize=subtitle_fontsize)
        axes = plt.gca()
        axes.set_ylim([0,0.1])

    print("Saving to: ", f"{output}_gke.png")
    plt.savefig(f"{output}_gke.png")
    plt.clf()
    plt.cla()


    # pdcsi
    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.7)

    for col in pdcsi_cols:
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')
        dplt = sns.lineplot(data=df, x="Time", y=col)
        dplt.legend(labels=pdcsi_cols, bbox_to_anchor=(1.01, 1.01), loc='upper left', ncol=1, mode="expand", prop={'size': 8})
        dplt.set(ylabel = "Seconds of CPU time used per second")
        dplt.set_title("CPU Usage By PDCSI Container", fontsize=subtitle_fontsize)
        axes = plt.gca()
        axes.set_ylim([0,0.1])

    print("Saving to: ", f"{output}_pdcsi.png")
    plt.savefig(f"{output}_pdcsi.png")
    plt.clf()
    plt.cla()


    # other
    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.65)

    for col in other_cols:
        df[col] = df[col].replace("undefined", "nan")
        df[col] = df[col].astype(float, errors='ignore')
        dplt = sns.lineplot(data=df, x="Time", y=col)
        dplt.legend(labels=other_cols, bbox_to_anchor=(1.01, 1.01), loc='upper left', ncol=1, mode="expand", prop={'size': 8})
        dplt.set(ylabel = "Seconds of CPU time used per second")
        dplt.set_title("CPU Usage By Miscellaneous Other Containers (e.g., No Other Category)", fontsize=subtitle_fontsize)
        axes = plt.gca()
        axes.set_ylim([0,0.1])

    print("Saving to: ", f"{output}_other_.png")
    plt.savefig(f"{output}_other.png")
    plt.clf()
    plt.cla()

    cols = []
    for col in df.columns:
        if col != "Time":
            cols.append(col)

    fig = plt.gcf()
    fig.set_size_inches(12, 5)
    plt.subplots_adjust(right=0.7)

    df["cpu_all"] = df[cols].sum(axis=1)
    df["cpu_all"] = df["cpu_all"].replace("undefined", "nan")
    df["cpu_all"] = df["cpu_all"].astype(float, errors='ignore')
    hplt = sns.lineplot(data=df, x="Time", y="cpu_all")
    hplt.set(ylabel="Seconds of CPU time used per second")
    hplt.set_title("Sum of CPU Usage Of All Containers")

    print("Saving to: ", f"{output}_aggregated.png")
    plt.savefig(f"{output}_aggregated.png")
    plt.clf()
    plt.cla()

    return (df["Time"], df["cpu_all"])

def compare_cpu_usages():
    users = ["100", "200", "300", "400", "500"]
    filter_types = ["no_filter", "empty_filter", "snicket_filter", "snicket_filter_distributed"]
    # everything should be in columns labeled:  cpu usage, users, filter type
    all_data = pd.DataFrame()
    for user in users:
        for filter_type in filter_types:
            csv_path = f"CPU_usage_time_{user}_users_{filter_type}.csv"
            df = pd.read_csv(csv_path)
            # 1. preprocess time
            df["Time"] = df["Time"].str[3:]
            df["Time"] = df["Time"].str[:21]
            df["Time"] = pd.to_datetime(df["Time"], infer_datetime_format=True)
            df["Time"] = df["Time"] - df["Time"][0] # normalize time

            # 2. get cpu_all, with startup data discarded
            cols = []
            for col in df.columns:
                if col != "Time":
                    cols.append(col)

            df["cpu_all"] = df[cols].sum(axis=1)
            df["cpu_all"] = df["cpu_all"].replace("undefined", "nan")
            df["cpu_all"] = df["cpu_all"].astype(float, errors='ignore')
            # here we remove the first few entries because locust was starting up
            # for 100-300, we remove 6 entries, which is equivalent to 60 sec
            # because the size of the spawn rate was 5
            # for 400 we remove 8, and for 500 we remove 10
            if user == '100' or user == '200' or user == '300':
                df["cpu_all"] = df["cpu_all"][5:]
            elif user == '400':
                df["cpu_all"] = df["cpu_all"][10:]
            else:
                df["cpu_all"] = df["cpu_all"][15:]

            df["cpu_all"] = df["cpu_all"].replace("undefined", "nan")
            df["cpu_all"] = df["cpu_all"].astype(float, errors='ignore')

            # 3. Save in a way that makes this plot-able later
            #    this means that you have three columns:  Value, Users, Filter
            # new_df = df["cpu_all"].copy()
            new_df = df.filter(['cpu_all'], axis=1)
            new_df.insert(1, 'users', user)
            new_df.insert(2, 'filter_type', filter_type)
            all_data = pd.concat([all_data, new_df])
            

    all_data = all_data.dropna(axis=0)
    ax = sns.barplot(data=all_data, x='users', y='cpu_all', hue='filter_type', estimator=median, ci="sd")
    plt.savefig(f"cpu_plot.png")




def main(args):
    #return graph(args.title, args.source, args.output)
    return compare_cpu_usages()

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
