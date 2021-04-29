#![feature(test)]
mod helpers;
mod integration_tests;
use test_filter_outputs::network_costs::run_query;

fn main() {
    run_query(
        "service_name",
        "get_service_name.cql",
        vec![],
        "productpage-v1\n",
        None,
        false,
    );
    run_query(
        "height",
        "height.cql",
        vec!["height.rs"],
        "2\n",
        None,
        false,
    );
    run_query(
        "request_size_avg",
        "request_size_avg.cql",
        vec!["avg.rs"],
        "1\navg: 1\n",
        Some("../tracing_sim/target/debug/libaggregation_example"),
        false,
    );
    run_query(
        "request_size_avg_trace_attr",
        "request_size_avg_trace_attr.cql",
        vec!["avg.rs"],
        "1\navg: 1\n",
        Some("../tracing_sim/target/debug/libaggregation_example"),
        false,
    );
    run_query(
        "request_size_avg_trace_attr",
        "request_size_avg_trace_attr.cql",
        vec!["avg.rs"],
        "1\navg: 1\n",
        Some("../tracing_sim/target/debug/libaggregation_example"),
        false,
    );
}
