#![feature(command_access)]
#[cfg(test)]
mod tests { 
    use sim;
    use std::collections::HashMap;
    use std::path::PathBuf;
    use std::env;
    use std::process::Command;
    use std::io::{self, Write};
    use std::fs::remove_dir_all;
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


    fn generate_filter_code(query_name: &str, udf_name: &str, directories: &HashMap<&'static str, PathBuf>) {
        let cmd = &mut directories["COMPILER_BINARY"].clone();
        assert!(cmd.exists());

        let mut my_args : Vec<&str> = Vec::new();
        
        let query_flag = "--query";
        let query_pathbuf = &mut directories["QUERY_DIR"].clone();
        query_pathbuf.push(query_name);
        assert!(query_pathbuf.exists());
        my_args.push(&query_flag);
        my_args.push(query_pathbuf.to_str().unwrap());

        let udf_flag = "-u";
        let udf_pathbuf = &mut directories["UDF_DIR"].clone();
        udf_pathbuf.push(udf_name);
        assert!(udf_pathbuf.exists());
        my_args.push(udf_flag);
        my_args.push(udf_pathbuf.to_str().unwrap());

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

    fn move_filter_dir(directories: &HashMap<&'static str, PathBuf>) {
        match remove_dir_all(&directories["TARGET_FILTER_DIR"]) {
            Ok(_) => {},
            Err(_) => { print!("Error removing the filter directory\n") },
        };
        let mut cmd = Command::new("cp");
        let args = ["-r", &directories["FILTER_DIR"].to_str().unwrap(), &directories["TARGET_FILTER_DIR"].to_str().unwrap()];
        cmd.args(&args);
        let output = cmd.output().expect("failed to copy filter over");
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();
        
        assert!(output.status.success());
    }

    fn compile_filter_dir(mut manifest_path: PathBuf) {
        manifest_path.push("Cargo.toml");
        let args = ["build", "--manifest-path", manifest_path.to_str().unwrap()];
        let mut cmd = Command::new("cargo");
        cmd.args(&args);
        let output = cmd.output().expect("failed to compile directory");
        io::stdout().write_all(&output.stdout).unwrap();
        io::stdout().write_all(&output.stderr).unwrap();
        assert!(output.status.success());
    }

    fn make_simulator(plugin_name: &mut PathBuf) -> sim::simulator::Simulator {
        plugin_name.push("target/debug/librust_filter");
        let plugin = Some(plugin_name.to_str().unwrap());

        let mut simulator = sim::simulator::Simulator::new(0); // always run with the seed 0

        let regular_nodes = ["frontend-v1", "cartservice-v1", "productcatalogservice-v1",
                             "currencyservice-v1", "paymentservice-v1", "shippingservice-v1",
                             "emailservice-v1", "checkoutservice-v1", "recomendationservice-v1",
                             "adservice-v1"].to_vec();
        for node in &regular_nodes {
            // node: ID, capacity, egress rate, generation rate, plugin
            simulator.add_node(node, 10, 2, 0, plugin);
        }
        simulator.add_node("loadgenerator-v1", 10, 1, 1, None);
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
        simulator.add_edge(1, "recomendationservice-v1", "productcatalogservice-v1", false);

        // src: checkout service
        simulator.add_edge(1, "checkoutservice-v1", "shippingservice-v1", false);
        simulator.add_edge(1, "checkoutservice-v1", "paymentservice-v1", false);
        simulator.add_edge(1, "checkoutservice-v1", "emailservice-v1", false);

        return simulator;
    }



    macro_rules! testit {
        ($name:ident, $query_name: expr, $udfs:expr, $expected_output:expr) => {
            #[test]
            fn $name() {
                let directories_wrapped = get_dirs();
                assert!(directories_wrapped!=None);
                let directories = directories_wrapped.unwrap();

                generate_filter_code($query_name, $udfs, &directories);
                move_filter_dir(&directories);
                compile_filter_dir(directories["TARGET_FILTER_DIR"].clone());
                let mut simulator = make_simulator(&mut directories["TARGET_FILTER_DIR"].clone());
                for tick in 0..10 {
                    simulator.tick(tick);
                }
                print!("{}", simulator.query_storage(STORAGE_NAME));
                assert_eq!($expected_output, simulator.query_storage(STORAGE_NAME));
            }
        }
    }

    testit!(count, "count.cql", "count.rs", "1");

}

fn main() {
    print!("Don't use cargo +nightly run, this is a test file, so use cargo +nightly test\n");
}
