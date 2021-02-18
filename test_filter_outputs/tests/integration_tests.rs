#![feature(command_access)]
#[cfg(test)]

mod tests {

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
        args.push(&str_builder);
        let filter_file = test_dir.join("filter.rs");
        let output_flag = "-o";
        args.push(output_flag);
        args.push(filter_file.to_str().unwrap());
        args.push("-c");
        args.push("sim");
        args.push("-r");
        args.push(ROOT_NAME);

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

    // Count is weird - if you make the nodes have the same names, as makes sense to me, then it doesn't work with c++
    // but I'm not sure what exactly the query is saying if they have different names - so we'll leave it for now until
    // we get language semantics ironed out
    #[test_case(
        "breadth_histogram",
        "breadth_histogram.cql",
        vec!["histogram.rs"],
        "Hist:  (1, 1) \n\nHist:  (1, 2) \n\nHist:  (1, 3) \n\nHist:  (1, 4) \n\nHist:  (1, 5) \n\nHist:  (1, 6) \n\nHist:  (1, 7) \n\n" ; "breadth_histogram_test"
    )]
    #[test_case(
        "height_histogram",
        "height_histogram.cql",
        vec!["histogram.rs"],
        "Hist:  (2, 1) \n\nHist:  (2, 2) \n\nHist:  (2, 3) \n\nHist:  (2, 4) \n\nHist:  (2, 5) \n\nHist:  (2, 6) \n\nHist:  (2, 7) \n\n" ; "height_histogram_test"
    )]
    #[test_case(
        "response_code_count",
        "response_code_count.cql",
        vec!["count.rs"],
        "1\n2\n3\n4\n5\n6\n7\n" ; "response_code_count_test"
    )]
    #[test_case(
        "response_size_avg",
        "response_size_avg.cql",
        vec!["avg.rs"],
        "1\n1\n1\n1\n1\n1\n1\n" ; "response_size_avg_test"
    )]
    #[test_case(
        "return_test",
        "return.cql",
        vec![],
        "1\n1\n1\n1\n1\n1\n1\n" ; "return_test"
    )]
    #[test_case(
        "return_height",
        "return_height.cql",
        vec![],
        "2\n2\n2\n2\n2\n2\n2\n" ; "return_height_test"
    )]
    fn test(query_id: &str, query_name: &str, udfs: Vec<&str>, expected_output: &str) {
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
        );
        compile_filter_dir(&filter_test_dir);

        // 4. Create the simulator and test the output
        let mut bookinfo_sim = example_envs::bookinfo::new_bookinfo(0, None);
        for tick in 0..10 {
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
