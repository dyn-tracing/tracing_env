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
    const ROOT_NAME: &str = "frontend-v1_plugin";
    const STORAGE_NAME: &str = "storage";

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
                to_return.insert("FILE_DIR", exe_path);
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
        my_args.push("filter");

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

    fn move_filter_dir(target_dir: String, directories: &HashMap<&'static str, PathBuf>) {
        match remove_dir_all(&target_dir) {
            Ok(_) => {}
            Err(_) => {
                print!("Error removing the filter directory\n")
            }
        };
        let mut cmd = Command::new("cp");
        let args = [
            "-r",
            &directories["FILTER_DIR"].to_str().unwrap(),
            &target_dir,
        ];
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
            "frontend-v1",
            "cartservice-v1",
            "productcatalogservice-v1",
            "currencyservice-v1",
            "paymentservice-v1",
            "shippingservice-v1",
            "emailservice-v1",
            "checkoutservice-v1",
            "recomendationservice-v1",
            "adservice-v1",
        ]
        .to_vec();
        for node in &regular_nodes {
            // node: ID, capacity, egress rate, generation rate, plugin
            simulator.add_node(node, 10, 10, 0, plugin);
        }
        simulator.add_node("loadgenerator-v1", 10, 1, 1, plugin);
        simulator.add_node("sink", 10, 1, 0, None); // rpc sink
        simulator.add_storage(STORAGE_NAME);

        // add all connections to storage and to the sink - we want traces to be able to end arbitrarily
        for node in &regular_nodes {
            simulator.add_edge(1, node, STORAGE_NAME, true);
            simulator.add_edge(1, node, "sink", true);
        }

        // src: load generator
        simulator.add_edge(1, "loadgenerator-v1", "frontend-v1", true);

        // src: frontend
        simulator.add_edge(1, "frontend-v1", "frontend-v1", false);
        simulator.add_edge(1, "frontend-v1", "cartservice-v1", false);
        simulator.add_edge(1, "frontend-v1", "recomendationservice-v1", false);
        simulator.add_edge(1, "frontend-v1", "productcatalogservice-v1", false);
        simulator.add_edge(1, "frontend-v1", "shippingservice-v1", false);
        simulator.add_edge(1, "frontend-v1", "checkoutservice-v1", false);
        simulator.add_edge(1, "frontend-v1", "adservice-v1", false);

        // src: recomendation service
        simulator.add_edge(
            1,
            "recomendationservice-v1",
            "productcatalogservice-v1",
            false,
        );

        // src: checkout service
        simulator.add_edge(1, "checkoutservice-v1", "shippingservice-v1", false);
        simulator.add_edge(1, "checkoutservice-v1", "paymentservice-v1", false);
        simulator.add_edge(1, "checkoutservice-v1", "emailservice-v1", false);

        return simulator;
    }

    macro_rules! testit {
        ($name:ident, $query_id: expr, $query_name: expr, $udfs:expr, $expected_output:expr) => {
            #[test]
            fn $name() {
                let directories_wrapped = get_dirs();
                assert!(directories_wrapped != None);
                let directories = directories_wrapped.unwrap();

                generate_filter_code($query_name, $udfs, &directories);
                let mut target_filter_dir = directories["TARGET_FILTER_DIR"]
                    .to_str()
                    .unwrap()
                    .to_string();
                target_filter_dir.push_str($query_id);
                move_filter_dir(target_filter_dir.clone(), &directories);
                compile_filter_dir(target_filter_dir.clone());
                let mut simulator = make_simulator(target_filter_dir.clone());
                for tick in 0..10 {
                    simulator.tick(tick);
                    print!("{}", simulator.query_storage(STORAGE_NAME));
                }
                print!("{}", simulator.query_storage(STORAGE_NAME));
                assert_eq!($expected_output, simulator.query_storage(STORAGE_NAME));
                // clean up all the directories we've created
                delete_filter_dir(target_filter_dir.clone());
            }
        };
    }

    // This directs everything to storage, but it takes 3 hops for it to make it to storage, so we get 7 results
    testit!(
        count,
        "count",
        "count_rust.cql",
        Some("count.rs"),
        "1\n2\n3\n4\n5\n6\n7\n"
    );

    testit!(breadth_histogram, "breadth_histogram", "breadth_histogram.cql", Some("histogram.rs"),
           "Hist:  (1, 1) \n\nHist:  (1, 2) \n\nHist:  (1, 3) \n\nHist:  (1, 4) \n\nHist:  (1, 5) \n\nHist:  (1, 6) \n\nHist:  (1, 7) \n\n".to_string());
    testit!(height_histogram, "height_histogram", "height_histogram.cql", Some("histogram.rs"), 
           "Hist:  (2, 1) \n\nHist:  (2, 2) \n\nHist:  (2, 3) \n\nHist:  (2, 4) \n\nHist:  (2, 5) \n\nHist:  (2, 6) \n\nHist:  (2, 7) \n\n".to_string());
    testit!(response_code_count, "response_code_count", "response_code_count.cql", Some("count.rs"), "1\n2\n3\n4\n5\n6\n7\n");
    testit!(response_size_avg, "response_size_avg", "response_size_avg.cql", Some("avg.rs"), "1\n1\n1\n1\n1\n1\n1\n");

    testit!(test_return, "return", "return.cql", None, "");
    testit!(return_height, "return_height", "return_height.cql", None, "2\n2\n2\n2\n2\n2\n2\n");
}

fn main() {
    print!("Don't use cargo +nightly run, this is a test file, so use cargo +nightly test\n");
}
