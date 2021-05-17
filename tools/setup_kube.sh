#!/bin/bash

# Configuration for Ubuntu 18.04
FILE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
ENV_DIR="${FILE_DIR}/../kubernetes_env"
COMPILER_DIR="${FILE_DIR}/../tracing_compiler"
SIMULATOR_DIR="${FILE_DIR}/../tracing_sim"
cd ${FILE_DIR}/..

# Basics
sudo apt install -y apt-transport-https gnupg2 curl

# Fetch the sub modules
git submodule update --init --recursive


if [ "$(uname)" == "Darwin" ]; then
# Docker
brew install hyperkit
brew upgrade hyperkit
# Kubectl
brew install kubectl
# Minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-darwin-amd64
sudo install minikube-darwin-amd64 /usr/local/bin/minikube
rm -rf minikube-darwin-amd64
# Need to use docker because we are in a VM
minikube config set driver hyperkit
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
# Docker
sudo apt install -y docker.io
# Docker without sudo
sudo usermod -aG docker $USER
# Kubectl
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo touch /etc/apt/sources.list.d/kubernetes.list
echo "deb http://apt.kubernetes.io/ kubernetes-yakkety main" | sudo tee -a /etc/apt/sources.list.d/kubernetes.list
sudo apt update
sudo apt install -y kubectl
# Minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube_latest_amd64.deb
sudo dpkg -i minikube_latest_amd64.deb
rm minikube_latest_amd64.deb
# Need to use docker because we are in a VM
minikube config set driver docker

fi

# Configure minikube
# Bookinfo requires more memory
minikube config set memory 4096

# Need prometheus for the API
pip3 install --user prometheus-api-client
# download and unpack istio
cd $ENV_DIR && curl -L https://istio.io/downloadIstio | \
    ISTIO_VERSION=1.9.3 TARGET_ARCH=x86_64 sh - && cd -
# Create the bin directory
mkdir -p bin
# Download fortio
curl -L https://github.com/fortio/fortio/releases/download/v1.11.4/fortio-linux_x64-1.11.4.tgz \
 | tar --strip-components=2  -C bin usr/bin/fortio -xvzpf -
# Build the burst tool
make -C tools/parallel_curl/

# Remaining core deps
${FILE_DIR}/setup_sim.sh

# Login to docker after installation
newgrp docker

echo "Done with Kubernetes setup."
