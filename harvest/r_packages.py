#!/usr/bin/env python3
"""Harvest R spatial packages (sf, terra) from their exported functions' formals.

    python harvest/r_packages.py [--rscript PATH]

Asks R for every exported function of each package (getNamespaceExports) and its
arguments (formals): names, and default expressions as R writes them. An argument
without a default is required. terra's functions are mostly S4 generics, whose own
formals are often just x and ...; the method-specific arguments are not
listed by the generic, so the harvester adds every method's arguments (each method
takes a subset). Writes implementations/<software>/, called as package::function.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PACKAGES = {"sf": "sf", "terra": "terra"}  # registry software id: R package

R_CODE = r"""
suppressPackageStartupMessages(library(jsonlite))
pkg <- commandArgs(trailingOnly = TRUE)[1]
suppressPackageStartupMessages(requireNamespace(pkg))
ns <- asNamespace(pkg)
out <- list(version = as.character(packageVersion(pkg)), functions = list())
for (name in sort(getNamespaceExports(pkg))) {
  f <- get0(name, envir = ns, inherits = FALSE)
  if (!is.function(f)) next
  fm <- tryCatch(formals(f), error = function(e) NULL)
  generic <- isGeneric(name, where = ns)
  if (generic) {
    # An S4 generic's own formals are often just (x, ...): add each method's arguments.
    for (m in tryCatch(findMethods(name, where = ns), error = function(e) list())) {
      fn <- m@.Data
      mf <- tryCatch(formals(fn), error = function(e) NULL)
      # A method with arguments its generic lacks is wrapped: the real function is the
      # `.local <- function(...)` at the top of its body.
      b <- body(fn)
      if (is.call(b) && length(b) >= 2 && is.call(b[[2]]) &&
          identical(b[[2]][[1]], as.name("<-")) && identical(b[[2]][[2]], as.name(".local"))) {
        lf <- tryCatch(eval(b[[2]][[3]]), error = function(e) NULL)
        if (is.function(lf)) mf <- formals(lf)
      }
      for (a in setdiff(names(mf), names(fm))) fm[a] <- mf[a]
    }
  }
  args <- list()
  for (a in names(fm)) {
    # An argument without a default is the empty symbol; never bind it to a variable.
    missing <- is.name(fm[[a]]) && nchar(as.character(fm[[a]])) == 0
    args[[length(args) + 1]] <- list(
      name = a,
      required = missing && a != "...",
      default = if (missing) NULL else paste(deparse(fm[[a]], width.cutoff = 200L), collapse = " "))
  }
  out$functions[[length(out$functions) + 1]] <- list(
    name = name, generic = generic, args = args)
}
cat(toJSON(out, auto_unbox = TRUE, null = "null"))
"""


def harvest(rscript: str, package: str, software: str) -> tuple[str, list[dict]]:
    out = subprocess.run([rscript, "--vanilla", "-e", R_CODE, package],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out[out.index("{"):])
    entries = []
    for f in data["functions"]:
        params = {}
        for a in f["args"]:
            if a["name"] == "...":
                params["..."] = common.param("dots", note="further arguments passed on")
                continue
            default = a.get("default")
            params[a["name"]] = common.param("any", required=a["required"],
                                             default=default if default not in (None, "") else None)
        entries.append(common.entry(
            id=common.slug(software, f["name"]), name=f"{package}::{f['name']}", software=software,
            interface="r", call_name=f"{package}::{f['name']}", harvester="r-packages",
            engine_version=data["version"], parameters=params,
            notes="S4 generic: parameters gathered from all its methods; each method takes a subset."
            if f.get("generic") else None))
    # R names can differ only by case or punctuation (st_cast vs st.cast): keep the first id.
    seen, unique = set(), []
    for e in entries:
        if e["id"] not in seen:
            seen.add(e["id"])
            unique.append(e)
    return data["version"], unique


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rscript", default="Rscript")
    ap.add_argument("--out", type=Path, default=common.IMPLEMENTATIONS)
    args = ap.parse_args()
    for software, package in PACKAGES.items():
        ver, entries = harvest(args.rscript, package, software)
        common.report(software, ver, common.write(software, entries, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
