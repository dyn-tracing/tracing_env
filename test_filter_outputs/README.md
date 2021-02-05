When you run these tests, make sure to run them with  `cargo +nightly test -- --test-threads=1`.  These tests cannot run in parallel since they are moving files/directories around.
