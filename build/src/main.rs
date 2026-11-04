use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};
use geo_registry::{default_path, entries, index, search, validate};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(
    name = "geo-registry",
    version,
    about = "Validate, build and search the Columbus geo-registry"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Clone, Copy, ValueEnum)]
enum Kind {
    Data,
    Tool,
}

impl Kind {
    fn as_str(self) -> &'static str {
        match self {
            Kind::Data => "data",
            Kind::Tool => "tool",
        }
    }
}

#[derive(Subcommand)]
enum Command {
    /// Validate every entry against the schema and the cross-entry rules.
    Validate {
        /// Entries directory (contains data/ and tools/).
        #[arg(long)]
        entries: Option<PathBuf>,
        /// JSON Schema file.
        #[arg(long)]
        schema: Option<PathBuf>,
    },
    /// Validate, then write index.json, registry.sqlite and index.sha256.
    Build {
        #[arg(long, default_value = "dist")]
        out: PathBuf,
        #[arg(long)]
        entries: Option<PathBuf>,
        #[arg(long)]
        schema: Option<PathBuf>,
    },
    /// Ranked full-text search over a built registry.sqlite.
    Search {
        query: String,
        #[arg(long, value_enum)]
        kind: Option<Kind>,
        #[arg(long)]
        db: Option<PathBuf>,
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
}

fn run_validate(
    entries_dir: Option<PathBuf>,
    schema: Option<PathBuf>,
) -> Result<Option<Vec<serde_json::Value>>> {
    let entries_dir = entries_dir.unwrap_or_else(|| default_path("entries"));
    let schema = schema.unwrap_or_else(|| default_path("schema/entry.schema.json"));
    let validator = validate::load_schema(&schema)?;
    let files = entries::load_dir(&entries_dir)?;
    let problems = validate::validate_files(&files, &validator);
    if problems.is_empty() {
        println!(
            "ok: {} entries in {} are valid",
            files.len(),
            entries_dir.display()
        );
        return Ok(Some(entries::values(&files)));
    }
    let mut bad: Vec<&str> = problems.iter().map(|p| p.file.as_str()).collect();
    bad.sort();
    bad.dedup();
    for p in &problems {
        eprintln!("error: {p}");
    }
    eprintln!(
        "\n{} problem(s) in {} file(s) out of {} entries",
        problems.len(),
        bad.len(),
        files.len()
    );
    Ok(None)
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    let result = match cli.command {
        Command::Validate { entries, schema } => {
            run_validate(entries, schema).map(|ok| ok.is_some())
        }
        Command::Build {
            out,
            entries,
            schema,
        } => run_validate(entries, schema).and_then(|ok| match ok {
            None => Ok(false),
            Some(values) => {
                let o = index::build(&values, &out)?;
                println!(
                    "built {} entries:\n  {}\n  {}\n  {}",
                    o.count,
                    o.index_json.display(),
                    o.sqlite.display(),
                    o.sha256.display()
                );
                Ok(true)
            }
        }),
        Command::Search {
            query,
            kind,
            db,
            limit,
        } => {
            let db = db.unwrap_or_else(|| default_path("dist/registry.sqlite"));
            search::search(&db, &query, kind.map(Kind::as_str), limit).map(|hits| {
                if hits.is_empty() {
                    println!("no results for {query:?}");
                }
                for (i, h) in hits.iter().enumerate() {
                    println!("{}", search::render(i, h));
                }
                true
            })
        }
    };
    match result {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(e) => {
            eprintln!("error: {e:#}");
            ExitCode::from(2)
        }
    }
}
