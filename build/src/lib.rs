//! Library behind the `geo-registry` CLI: load YAML entries, validate them
//! against the JSON Schema and the cross-entry rules, build the published
//! index (`index.json`, `registry.sqlite`, `index.sha256`) and search it.

pub mod entries;
pub mod index;
pub mod search;
pub mod validate;

use std::path::{Path, PathBuf};

/// Recipe tools the Columbus server exposes. Kept in sync with
/// `schema/entry.schema.json#/$defs/recipeTool`.
pub const RECIPE_TOOLS: &[&str] = &[
    "query_features",
    "vector_op",
    "raster_op",
    "pointcloud_pipeline",
    "registry_fetch",
];

/// Version of the `index.json` / `registry.sqlite` layout.
pub const FORMAT_VERSION: u32 = 1;

/// Resolve a default path that may live in the current directory or its
/// parent, so the CLI works both from the repo root and from `build/`.
pub fn default_path(rel: &str) -> PathBuf {
    let here = PathBuf::from(rel);
    if here.exists() {
        return here;
    }
    let parent = Path::new("..").join(rel);
    if parent.exists() {
        return parent;
    }
    here
}
