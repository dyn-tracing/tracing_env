#[cfg(test)]
mod tests {
    use crate::helpers::generate_filter_code;
    use crate::helpers::compile_filter_dir;
    use test_case::test_case;
    use rpc_lib::rpc::Rpc;
    const STORAGE_NAME: &str = "storage";
    use std::path::Path;
    use std::fs;

    #[test_case(
        "service_name",
        "get_service_name.cql",
        vec![],
        "productpage-v1\n" ,
        None, false ; "service_name_test"
    )]
    #[test_case(
        "service_name_distributed",
        "get_service_name.cql",
        vec![],
        "productpage-v1\n" ,
        None, true ; "service_name_distributed_test"
    )]
    #[test_case(
        "height",
        "height.cql",
        vec!["height.rs"],
        "2\n",
        None , false ; "height_test"
    )]
    #[test_case(
        "height_distributed",
        "height.cql",
        vec!["height.rs"],
        "2\n",
        None , true ; "height_distributed_test"
    )]
    #[test_case(
        "request_size_avg",
        "request_size_avg.cql",
        vec![],
        "1\navg: 1\n",
        Some("../tracing_sim/target/debug/libaggregation_example"), false ; "request_size_avg_test"
    )]
    #[test_case(
        "request_size_avg_distributed",
        "request_size_avg.cql",
        vec![],
        "1\navg: 1\n",
        Some("../tracing_sim/target/debug/libaggregation_example"), true ; "request_size_avg_distributed_test"
    )]

    #[test_case(
        "request_size_avg_trace_attr",
        "request_size_avg_trace_attr.cql",
        vec![],
        "1\navg: 1\n",
        Some("../tracing_sim/target/debug/libaggregation_example"), false ; "request_size_avg_trace_attr_test"
    )]
    #[test_case(
        "request_size_avg_trace_attr_distributed",
        "request_size_avg_trace_attr.cql",
        vec![],
        "1\navg: 1\n",
        Some("../tracing_sim/target/debug/libaggregation_example"), true ; "request_size_avg_trace_attr_distributed_test"
    )]
    #[test_case(
        "return_trace",
        "return_trace.cql",
        vec![],
        "trace_graph",
        None, false ; "return_trace_test"
    )]

    fn test(
        query_id: &str,
        query_name: &str,
        udfs: Vec<&str>,
        expected_output: &str,
        aggregation_id: Option<&str>,
        distributed: bool,
    ) {
        // 1.Create the necessary directories
        let file_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
        let filter_test_dir = file_dir.join("filters").join(query_id);
        let compiler_dir = file_dir.join("../tracing_compiler");
        let generic_cargo = file_dir.join("generic_cargo.toml");
        let dst_cargo = filter_test_dir.join("Cargo.toml");

        match fs::create_dir_all(filter_test_dir.to_owned()) {
            Ok(_) => {}
            Err(_) => {
                panic!("Error creating the filter directory.\n")
            }
        };

        // 2. copy filter directory over from rust_filter
        match fs::copy(generic_cargo, dst_cargo) {
            Ok(_) => {}
            Err(_) => {
                panic!("Error copying the TOML template into the target directory.\n")
            }
        };
        // 3. generate the filter file into that directory and compile
        generate_filter_code(
            compiler_dir.as_path(),
            filter_test_dir.as_path(),
            query_name,
            udfs,
            distributed
        );
        compile_filter_dir(&filter_test_dir);
        let filter_plugin = filter_test_dir.join("target/debug/librust_filter");

        // 4. Create the simulator and test the output
        let mut bookinfo_sim =
            example_envs::bookinfo::new_bookinfo(0, None, filter_plugin.to_str(), aggregation_id);
        bookinfo_sim.insert_rpc("gateway", Rpc::new("0"));
        for tick in 0..7 {
            bookinfo_sim.tick(tick);
        }
        assert!(bookinfo_sim.query_storage(STORAGE_NAME).contains(expected_output), "output was {:?}", bookinfo_sim.query_storage(STORAGE_NAME));

        // 5. clean up the temporary filter directory
        match fs::remove_dir_all(filter_test_dir) {
            Ok(_) => {}
            Err(e) => {
                println!("Error deleting the filter directory: {:?}\n", e)
            }
        };
    }
}
