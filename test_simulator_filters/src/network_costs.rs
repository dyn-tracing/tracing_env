use crate::helpers::compile_filter_dir;
use crate::helpers::generate_filter_code;
use rpc_lib::rpc::Rpc;
use std::fs;
use std::fs::File;
use std::io::prelude::*;
use std::path::Path;
const STORAGE_NAME: &str = "storage";

fn read_and_delete_csv(file_name: String, test_name: &str) {
    let mut file = File::open(file_name.clone()).unwrap();
    let mut contents = String::new();
    file.read_to_string(&mut contents).unwrap();

    let mut total = 0;
    let mut reader = csv::Reader::from_reader(contents.as_bytes());
    for record in reader.records() {
        match record {
            Ok(r) => {
                total += r[1].parse::<i64>().unwrap();
            }
            Err(e) => {
                print!("error: {0}", e);
            }
        }
    }
    println!("Test {0} resulted in {1} network cost", test_name, total);

    match fs::remove_file(file_name) {
        Ok(_) => {}
        Err(e) => {
            println!("Error:  could not remove file because {0}", e);
        }
    }
}

pub fn run_query(
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
    let result_file = format!("{0}_result.csv", query_id);
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
        distributed,
    );
    compile_filter_dir(&filter_test_dir);
    let filter_plugin = filter_test_dir.join("target/debug/librust_filter");

    // 4. Create the simulator and test the output
    let mut bookinfo_sim = example_envs::bookinfo::new_bookinfo(
        0,
        Some(result_file.clone()),
        filter_plugin.to_str(),
        aggregation_id,
    );
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

    // 6. Find and print the results and delete file
    read_and_delete_csv(result_file, query_id);
}
