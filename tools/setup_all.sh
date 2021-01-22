#!/bin/bash

# pytest for testing
pip3 install --user pytest

# install all Kubernetes dependencies
./setup_kube.sh
# build the compiler
./setup_sim.sh

echo "Done with setup."
