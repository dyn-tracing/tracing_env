#!/bin/bash

# Configuration for Ubuntu 18.04
FILE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
ENV_DIR="${FILE_DIR}/../kubernetes_env"
COMPILER_DIR="${FILE_DIR}/../tracing_compiler"
SIMULATOR_DIR="${FILE_DIR}/../tracing_sim"
cd ${FILE_DIR}/..

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
set PATH $HOME/.cargo/bin $PATH
rustup toolchain install nightly
# we need to use nightly as default
rustup default nightly
# install the wasm back end
rustup target add wasm32-unknown-unknown --toolchain nightly

# Now start building the compiler
cargo build --manifest-path ${COMPILER_DIR}/Cargo.toml
# and also build the simulator
cargo build --manifest-path ${SIMULATOR_DIR}/Cargo.toml

# Install pytest for testing
pip3 install --user pytest
# Install requests for API requests (needed here because of imports)
pip3 install --user requests

# Install seaborn for benchmarking
pip3 install --user seaborn

# Install locust for benchmarking
pip3 install --user locust
echo "Done with simulator setup."
