load("@rules_proto//proto:defs.bzl", "proto_library")
load("//bazel/wasm:wasm.bzl", "wasm_cc_binary")
load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library", "cc_test")

proto_library(
    name = "filter_proto",
    srcs = [
        "filter.proto",
    ],
)

cc_proto_library(
    name = "filter_cc_proto",
    deps = [":filter_proto"],
)

wasm_cc_binary(
    name = "filter.wasm",
    srcs = [
        "filter.cc",
    ],
    additional_linker_inputs = ["@proxy_wasm_cpp_sdk//:jslib"],
    linkopts = [
        "--js-library",
        "external/proxy_wasm_cpp_sdk/proxy_wasm_intrinsics.js",
    ],
    deps = [
        "@proxy_wasm_cpp_sdk//:proxy_wasm_intrinsics",
         ":graph_utils",
        ":str_utils",
    ],
)

cc_library(
    name = "str_utils",
    srcs = [
        "str_utils.cc",
    ],
    hdrs = [
        "str_utils.h",
    ],
)

cc_library(
    name = "graph_utils",
    srcs = [
        "graph_utils.cc",
    ],
    hdrs = [
        "graph_utils.h",
    ],
    deps = [
        "@boost//:graph",
        ":str_utils",
    ],
)
