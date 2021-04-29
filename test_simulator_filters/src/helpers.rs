use std::io::{self, Write};
use std::path::Path;
use std::process::Command;

// used for testing, so clippy thinks it's unused
#[allow(dead_code)] 
pub fn generate_filter_code(
    compiler_dir: &Path,
    test_dir: &Path,
    query_name: &str,
    udf_names: Vec<&str>,
    distributed: bool,
) {
    const ROOT_NAME: &str = "productpage-v1";
    let compile_cmd = compiler_dir.join("target/debug/snicket");
    assert!(compile_cmd.exists());

    let mut args: Vec<&str> = Vec::new();

    let query_flag = "--query";
    let query = compiler_dir.join("example_queries").join(query_name);

    assert!(query.exists());
    args.push(&query_flag);
    args.push(query.to_str().unwrap());

    let udf_dir = compiler_dir.join("example_udfs");
    if !udf_names.is_empty() {
        args.push("-u");
    }
    let mut udfs_full = Vec::new();
    for udf_name in udf_names {
        let udf_full = udf_dir.join(udf_name).to_str().unwrap().to_string();
        udfs_full.push(udf_full);
    }
    for udf in &udfs_full {
        args.push(udf);
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
    }

    let mut cmd_obj = Command::new(compile_cmd);
    cmd_obj.args(args);
    //print!("args: {:?}", &args);

    let output = cmd_obj.output().expect("failed to execute process");

    // these prints will only actually print if the function fails
    io::stdout().write_all(&output.stdout).unwrap();
    io::stdout().write_all(&output.stderr).unwrap();
    assert!(output.status.success());
}

// used for testing, so clippy thinks it's unused
#[allow(dead_code)] 
pub fn compile_filter_dir(filter_test_dir: &Path) {
    let manifest_path = filter_test_dir.join("Cargo.toml");
    let args = ["build", "--manifest-path", manifest_path.to_str().unwrap()];
    let mut cmd = Command::new("cargo");
    cmd.args(&args);
    let output = cmd.output().expect("failed to compile directory");
    io::stdout().write_all(&output.stdout).unwrap();
    io::stdout().write_all(&output.stderr).unwrap();
    assert!(output.status.success());
}
