#![feature(command_access)]
#[cfg(test)]

mod tests {
    use sim;
    use std::collections::HashMap;
    use std::env;
    use std::fs::remove_dir_all;
    use std::io::{self, Write};
    use std::path::PathBuf;
    use std::process::Command;
    use test_case::test_case;
    const ROOT_NAME: &str = "productpage-v1";
    const STORAGE_NAME: &str = "storage";

    // all the correct results
    // Because you can't do this sort of computation outside a function, I've made a function
    // to get all the directories/files
    fn get_dirs() -> Option<HashMap<&'static str, PathBuf>> {
        let mut to_return = HashMap::new();
        match env::current_exe() {
            Ok(mut exe_path) => {
                // our executeable is in target/debug/... these pops are to get out of that directory into tracing_env
                for _i in 0..5 {
                    exe_path.pop();
                }

                let mut sim_dir = exe_path.clone();
                sim_dir.push("tracing_sim");

                let mut compiler_dir = exe_path.clone();
                compiler_dir.push("tracing_compiler");

                let mut filter_dir = compiler_dir.clone();
                filter_dir.push("rust_filter");
                to_return.insert("FILTER_DIR", filter_dir);

                let mut compiler_binary = compiler_dir.clone();
                compiler_binary.push("target/debug/dtc");
                to_return.insert("COMPILER_BINARY", compiler_binary);

                let mut query_dir = compiler_dir.clone();
                query_dir.push("example_queries");
                to_return.insert("QUERY_DIR", query_dir);

                let mut udf_dir = compiler_dir.clone();
                udf_dir.push("example_udfs");
                to_return.insert("UDF_DIR", udf_dir);

                let mut target_filter_dir = sim_dir.clone();
                target_filter_dir.push("libs/rust_filter");
                to_return.insert("TARGET_FILTER_DIR", target_filter_dir);

                to_return.insert("COMPILER_DIR", compiler_dir);
                to_return.insert("ENV_DIR", exe_path);
                to_return.insert("SIM_DIR", sim_dir);
                return Some(to_return);
            }
            Err(e) => {
                println!("failed to get current exe path: {}", e);
                return None;
            }
        };
    }

    fn generate_filter_code(
        query_name: &str,
        filter_dir: &mut PathBuf,
        udf_name: Option<&str>,
        directories: &HashMap<&'static str, PathBuf>,
    ) {
        let cmd = &mut directories["COMPILER_BINARY"].clone();
        assert!(cmd.exists());

        let mut my_args: Vec<&str> = Vec::new();

        let query_flag = "--query";
        let query_pathbuf = &mut directories["QUERY_DIR"].clone();
        query_pathbuf.push(query_name);
        assert!(query_pathbuf.exists());
        my_args.push(&query_flag);
        my_args.push(query_pathbuf.to_str().unwrap());

        let mut udf_pathbuf;
        if !udf_name.is_none() {
            let udf_flag = "-u";
            udf_pathbuf = directories["UDF_DIR"].clone();
            udf_pathbuf.push(udf_name.unwrap());
            assert!(udf_pathbuf.exists());
            my_args.push(udf_flag);
            my_args.push(udf_pathbuf.to_str().unwrap());
        }

        let output_flag = "-o";
        my_args.push(output_flag);
        filter_dir.push("filter.rs");
        my_args.push(filter_dir.to_str().unwrap());

        my_args.push("-c");
        my_args.push("sim");
        my_args.push("-r");
        my_args.push(ROOT_NAME);

        let mut cmd_obj = Command::new(cmd);
        cmd_obj.args(my_args);

        let output = cmd_obj.output().expect("failed to execute process");

        // these prints will only actually print if the function fails
        println!("status: {}", output.status);
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();
        assert!(output.status.success());
    }

    fn overwrite_toml(target_dir: &str, cargo: &str) {
        let mut cmd = Command::new("cp");
        let mut target_toml = target_dir.to_string();
        target_toml.push_str("/Cargo.toml");
        print!("copying from {0} to {1}\n", cargo, &target_toml);
        let args = [ cargo, &target_toml ];
        cmd.args(&args);
        let output = cmd.output().expect("failed to copy filter over");
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();

        assert!(output.status.success());
    }
    fn copy_filter_dir(target_dir: &str, source_dir: &str) {
        match remove_dir_all(&target_dir) {
            Ok(_) => {}
            Err(_) => {
                print!("Error removing the filter directory\n")
            }
        };
        let mut cmd = Command::new("cp");
        let args = ["-r", &source_dir, &target_dir];
        cmd.args(&args);
        let output = cmd.output().expect("failed to copy filter over");
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();

        assert!(output.status.success());
    }
    fn delete_filter_dir(target_dir: String) {
        match remove_dir_all(&target_dir) {
            Ok(_) => {}
            Err(_) => {
                print!("Error removing the filter directory\n")
            }
        };
    }

    fn compile_filter_dir(mut manifest_path: String) {
        manifest_path.push_str("/Cargo.toml");
        print!("manifest path is {0}\n", manifest_path);
        let args = ["build", "--manifest-path", &manifest_path];
        let mut cmd = Command::new("cargo");
        cmd.args(&args);
        let output = cmd.output().expect("failed to compile directory");
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();
        assert!(output.status.success());
    }

    fn make_simulator(mut plugin_name: String) -> sim::simulator::Simulator {
        plugin_name.push_str("/target/debug/librust_filter");
        let plugin = Some(plugin_name.as_str());

        let mut simulator = sim::simulator::Simulator::new(1); // always run with the seed 1

        let regular_nodes = [
            "productpage-v1",
            "ratings-v1",
            "reviews-v1",
            "reviews-v2",
            "reviews-v3",
            "details-v1",
        ]
        .to_vec();
        simulator.add_node("productpage-v1", 10, 5, 0, plugin);
        simulator.add_node("reviews-v1", 10, 5, 0, plugin);
        simulator.add_node("reviews-v2", 10, 5, 0, plugin);
        simulator.add_node("reviews-v3", 10, 5, 0, plugin);

        // ratings and details are dead ends
        simulator.add_node("ratings-v1", 10, 0, 0, plugin);
        simulator.add_node("details-v1", 10, 0, 0, plugin);
        simulator.add_node("loadgenerator-v1", 10, 1, 1, None);
        simulator.add_storage(STORAGE_NAME);

        // add all connections to storage
        for node in &regular_nodes {
            simulator.add_edge(1, node, STORAGE_NAME, true);
        }

        // src: traffic generator
        simulator.add_edge(1, "loadgenerator-v1", "productpage-v1", true);
        // src: product page
        simulator.add_edge(1, "productpage-v1", "reviews-v1", false);
        simulator.add_edge(1, "productpage-v1", "reviews-v2", false);
        simulator.add_edge(1, "productpage-v1", "reviews-v3", false);
        simulator.add_edge(1, "productpage-v1", "details-v1", true);
        // src: reviews
        simulator.add_edge(1, "reviews-v1", "ratings-v1", false);
        simulator.add_edge(1, "reviews-v2", "ratings-v1", false);
        simulator.add_edge(1, "reviews-v3", "ratings-v1", false);
        return simulator;
    }

    // Count is weird - if you make the nodes have the same names, as makes sense to me, then it doesn't work with c++
    // but I'm not sure what exactly the query is saying if they have different names - so we'll leave it for now until
    // we get language semantics ironed out
    #[test_case(
        "breadth_histogram",
        "breadth_histogram.cql",
        Some("histogram.rs"),
        "Hist:  (1, 1) \n\nHist:  (1, 2) \n\nHist:  (1, 3) \n\nHist:  (1, 4) \n\nHist:  (1, 5) \n\nHist:  (1, 6) \n\nHist:  (1, 7) \n\n" ; "breadth_histogram_test"
    )]
    #[test_case(
        "height_histogram",
        "height_histogram.cql",
        Some("histogram.rs"),
        "Hist:  (2, 1) \n\nHist:  (2, 2) \n\nHist:  (2, 3) \n\nHist:  (2, 4) \n\nHist:  (2, 5) \n\nHist:  (2, 6) \n\nHist:  (2, 7) \n\n" ; "height_histogram_test"
    )]
    #[test_case(
        "response_code_count",
        "response_code_count.cql",
        Some("count.rs"),
        "1\n2\n3\n4\n5\n6\n7\n" ; "response_code_count_test"
    )]
    #[test_case(
        "response_size_avg",
        "response_size_avg.cql",
        Some("avg.rs"),
        "1\n1\n1\n1\n1\n1\n1\n" ; "response_size_avg_test"
    )]
    #[test_case(
        "return_test",
        "return.cql",
        None,
        "1\n1\n1\n1\n1\n1\n1\n" ; "return_test"
    )]
    #[test_case(
        "return_height",
        "return_height.cql",
        None,
        "2\n2\n2\n2\n2\n2\n2\n" ; "return_height_test"
    )]
    fn test(query_id: &str, query_name: &str, udfs: Option<&str>, expected_output: &str) {
        // 1. get directories
        let directories_wrapped = get_dirs();
        assert!(directories_wrapped != None);
        let directories = directories_wrapped.unwrap();

        //let temp_dir_buf = &mut directories["SIM_DIR"].clone();
        //temp_dir_buf.push("libs");
        //temp_dir_buf.push(query_id);
        let temp_dir_buf = &mut directories["ENV_DIR"].clone();
        temp_dir_buf.push(query_id);
        let temp_dir = temp_dir_buf.to_str().unwrap().to_string();
        

        // 2. copy filter directory over from rust_filter
        print!(
            "copying from {0} to {1}\n",
            directories["FILTER_DIR"].to_str().unwrap(),
            temp_dir
        );
        copy_filter_dir(&temp_dir, directories["FILTER_DIR"].to_str().unwrap());
        let cargo = &mut directories["ENV_DIR"].clone();
        cargo.push("test_filter_outputs");
        cargo.push("generic_cargo.toml");
        overwrite_toml(&temp_dir, cargo.to_str().unwrap());

        // 3. generate the filter file into that directory and compile
        generate_filter_code(query_name, temp_dir_buf, udfs, &directories);
        compile_filter_dir(temp_dir.clone());

        // 4. make the simulator and test outputs
        let mut simulator = make_simulator(temp_dir.clone());
        for tick in 0..10 {
            simulator.tick(tick);
            print!("{}", simulator.query_storage(STORAGE_NAME));
        }
        print!("{}", simulator.query_storage(STORAGE_NAME));
        assert_eq!(expected_output, simulator.query_storage(STORAGE_NAME));

        // 5. clean up the temporary filter directory
        delete_filter_dir(temp_dir);
    }
}
