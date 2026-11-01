//! On macOS an extension module leaves the Python symbols undefined for the interpreter to provide; this passes
//! `-undefined dynamic_lookup` for every build (maturin, `cargo build`, `cargo test`), wherever cargo runs from.
fn main() {
    pyo3_build_config::add_extension_module_link_args();
}
