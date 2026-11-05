"""Export ArcGIS Pro's geoprocessing tools and their parameters, for the registry.

Run this in ArcGIS Pro's own Python, on a machine with ArcGIS Pro installed:

    "%PROGRAMFILES%\\ArcGIS\\Pro\\bin\\Python\\Scripts\\propy.bat" arcgis_pro_export.py

(or from the Python Command Prompt that comes with Pro: python arcgis_pro_export.py).
It writes arcgis-pro-tools.jsonl in the current folder: one line per tool with its
toolbox, name and parameters (name, data type, direction, required or optional,
default, list of allowed values). It reads tool descriptions only; it opens no
data and changes nothing. Then, anywhere with the registry checked out:

    python harvest/arcgis_pro.py arcgis-pro-tools.jsonl

Standard library and arcpy only, so nothing needs installing into Pro's Python.
No help text is exported: the registry keeps facts (names and types), not Esri's
documentation, which is under Esri's copyright.
"""

import json
import sys


def text(v):
    if v is None:
        return None
    try:
        s = str(v)
    except Exception:  # noqa: BLE001 - some values cannot be printed
        return None
    return s if s else None


def param_record(p):
    rec = {
        "name": p.name,
        "datatype": text(getattr(p, "datatype", None)),
        "direction": text(getattr(p, "direction", None)),
        "parameterType": text(getattr(p, "parameterType", None)),
        "multiValue": bool(getattr(p, "multiValue", False)),
        "default": text(getattr(p, "value", None)),
    }
    flt = getattr(p, "filter", None)
    if flt is not None and getattr(flt, "type", None) == "ValueList":
        try:
            rec["values"] = [text(v) for v in (flt.list or []) if text(v) is not None]
        except Exception:  # noqa: BLE001
            pass
    return rec


def main():
    import arcpy

    out_path = sys.argv[1] if len(sys.argv) > 1 else "arcgis-pro-tools.jsonl"
    info = arcpy.GetInstallInfo()
    count = errors = 0
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps({"product": info.get("ProductName"), "version": info.get("Version"),
                              "build": info.get("BuildNumber")}) + "\n")
        for toolbox in sorted(arcpy.ListToolboxes()):
            # "Analysis Tools(analysis)" -> name and alias
            if "(" not in toolbox:
                continue
            name, alias = toolbox[:-1].rsplit("(", 1)
            for tool in sorted(arcpy.ListTools("*_" + alias)):
                rec = {"toolbox": name.strip(), "alias": alias, "tool": tool[: -len(alias) - 1]}
                try:
                    rec["params"] = [param_record(p) for p in arcpy.GetParameterInfo(tool)]
                except Exception as e:  # noqa: BLE001 - record and carry on
                    rec["error"] = f"{type(e).__name__}: {e}"[:300]
                    errors += 1
                out.write(json.dumps(rec) + "\n")
                count += 1
    print(f"wrote {count} tools ({errors} could not be described) to {out_path}")


if __name__ == "__main__":
    main()
