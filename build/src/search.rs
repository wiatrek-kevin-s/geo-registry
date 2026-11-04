//! Ranked full-text search over `registry.sqlite`, for local testing.

use anyhow::{Context, Result};
use rusqlite::{params, Connection, OpenFlags};
use serde_json::Value;
use std::path::Path;

#[derive(Debug, Clone)]
pub struct Hit {
    pub rank: f64,
    pub card: Value,
}

/// Turn free text into a safe FTS5 query: every word is quoted (so FTS syntax
/// in user input is inert) and prefix-matched; words are ANDed.
pub fn fts_query(input: &str) -> Option<String> {
    let terms: Vec<String> = input
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(|w| format!("\"{}\"*", w.to_lowercase()))
        .collect();
    if terms.is_empty() {
        None
    } else {
        Some(terms.join(" "))
    }
}

/// Search the database. `kind` filters to `data` or `tool`. Retired entries
/// are ranked last. Column weights: name 10, summary 4, category 2, themes 3, notes 1.
pub fn search(db: &Path, query: &str, kind: Option<&str>, limit: usize) -> Result<Vec<Hit>> {
    let Some(q) = fts_query(query) else {
        return Ok(Vec::new());
    };
    let conn = Connection::open_with_flags(db, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .with_context(|| format!("opening {}", db.display()))?;
    let mut stmt = conn.prepare(
        "SELECT bm25(entries_fts, 0.0, 10.0, 4.0, 2.0, 3.0, 1.0) AS score, e.card
           FROM entries_fts
           JOIN entries e ON e.id = entries_fts.id
          WHERE entries_fts MATCH ?1
            AND (?2 IS NULL OR e.kind = ?2)
          ORDER BY (e.status = 'retired'), score, e.id
          LIMIT ?3",
    )?;
    let rows = stmt.query_map(params![q, kind, limit as i64], |r| {
        let score: f64 = r.get(0)?;
        let card: String = r.get(1)?;
        Ok((score, card))
    })?;
    let mut hits = Vec::new();
    for row in rows {
        let (score, card) = row?;
        hits.push(Hit {
            rank: -score,
            card: serde_json::from_str(&card)?,
        });
    }
    Ok(hits)
}

/// One-line rendering of a hit for the terminal.
pub fn render(i: usize, h: &Hit) -> String {
    let c = &h.card;
    let s = |k: &str| c.get(k).and_then(Value::as_str).unwrap_or("").to_string();
    let scope = if s("kind") == "data" {
        let access = c
            .get("access_types")
            .and_then(Value::as_array)
            .map(|a| {
                a.iter()
                    .filter_map(Value::as_str)
                    .collect::<Vec<_>>()
                    .join(",")
            })
            .unwrap_or_default();
        format!("{} | {}", s("region"), access)
    } else {
        s("category")
    };
    let mut summary = s("summary");
    if summary.chars().count() > 90 {
        summary = summary.chars().take(87).collect::<String>() + "...";
    }
    format!(
        "{:>2}. {} [{}] {:.2}\n    {} | {} | {} | {}\n    {}\n    {}",
        i + 1,
        s("name"),
        s("id"),
        h.rank,
        s("kind"),
        scope,
        s("license"),
        s("status"),
        summary,
        s("url")
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn query_is_quoted_and_prefixed() {
        assert_eq!(fts_query("LiDAR").unwrap(), "\"lidar\"*");
        assert_eq!(
            fts_query("point-cloud OR \"x").unwrap(),
            "\"point\"* \"cloud\"* \"or\"* \"x\"*"
        );
        assert!(fts_query("  -- ").is_none());
    }
}
