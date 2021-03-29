#![feature(command_access)]
#[cfg(test)]

mod tests {

    use rpc_lib::rpc::Rpc;
    use std::env;
    use std::fs;
    use std::io::{self, Write};
    use std::path::Path;
    use std::process::Command;
    use test_case::test_case;
    const ROOT_NAME: &str = "productpage-v1";
    const STORAGE_NAME: &str = "storage";

    fn generate_filter_code(
        compiler_dir: &Path,
        test_dir: &Path,
        query_name: &str,
        udf_names: Vec<&str>,
        distributed: bool,
    ) {
        let compile_cmd = compiler_dir.join("target/debug/dtc");
        assert!(compile_cmd.exists());

        let mut args: Vec<&str> = Vec::new();

        let query_flag = "--query";
        let query = compiler_dir.join("example_queries").join(query_name);

        assert!(query.exists());
        args.push(&query_flag);
        args.push(query.to_str().unwrap());

        let udf_dir = compiler_dir.join("example_udfs");
        let mut str_builder = String::new();
        for udf_name in udf_names {
            let udf_file = udf_dir.join(udf_name);
            str_builder.push_str("-u");
            str_builder.push_str(udf_file.to_str().unwrap());
        }
        if !str_builder.is_empty() {
            args.push(&str_builder);
        }
        let filter_file = test_dir.join("filter.rs");
        let output_flag = "-o";
        args.push(output_flag);
        args.push(filter_file.to_str().unwrap());
        args.push("-c");
        args.push("sim");
        args.push("-r");
        args.push(ROOT_NAME);

        if distributed {
            args.push("-d");
            args.push("true");
        }

        let mut cmd_obj = Command::new(compile_cmd);
        cmd_obj.args(args);

        let output = cmd_obj.output().expect("failed to execute process");

        // these prints will only actually print if the function fails
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();
        assert!(output.status.success());
    }

    fn compile_filter_dir(filter_test_dir: &Path) {
        let manifest_path = filter_test_dir.join("Cargo.toml");
        print!("manifest path is {:?}\n", manifest_path);
        let args = ["build", "--manifest-path", manifest_path.to_str().unwrap()];
        let mut cmd = Command::new("cargo");
        cmd.args(&args);
        let output = cmd.output().expect("failed to compile directory");
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();
        assert!(output.status.success());
    }

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
        "1",
        Some("../tracing_sim/target/debug/libaggregation_example"), false ; "request_size_avg_test"
    )]
    #[test_case(
        "request_size_avg_distributed",
        "request_size_avg.cql",
        vec![],
        "1",
        Some("../tracing_sim/target/debug/libaggregation_example"), true ; "request_size_avg_distributed_test"
    )]

    #[test_case(
        "request_size_avg_trace_attr",
        "request_size_avg_trace_attr.cql",
        vec![],
        "1",
        Some("../tracing_sim/target/debug/libaggregation_example"), false ; "request_size_avg_trace_attr_test"
    )]
    #[test_case(
        "request_size_avg_trace_attr_distributed",
        "request_size_avg_trace_attr.cql",
        vec![],
        "1",
        Some("../tracing_sim/target/debug/libaggregation_example"), true ; "request_size_avg_trace_attr_distributed_test"
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
        let simulator_dir = file_dir.join("../tracing_sim");
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
        assert_eq!(expected_output, bookinfo_sim.query_storage(STORAGE_NAME));

        // 5. clean up the temporary filter directory
        match fs::remove_dir_all(filter_test_dir) {
            Ok(_) => {}
            Err(_) => {
                panic!("Error deleting the filter directory.\n")
            }
        };
    }
}
