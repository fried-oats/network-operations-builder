"""Collect installed distribution metadata and bundled license texts for review."""
from importlib.metadata import distributions
from pathlib import Path
import json
import sys
import shutil

destination = Path(sys.argv[1]) / "licenses"
destination.mkdir(parents=True, exist_ok=True)
manifest = []
for distribution in distributions():
    name = distribution.metadata["Name"]
    manifest.append({"name": name, "version": distribution.version,
                     "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License", "See license files"),
                     "project_urls": distribution.metadata.get_all("Project-URL", [])})
    for file in distribution.files or []:
        if any(term in file.name.casefold() for term in ("license", "copying", "notice")):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                target = destination / name / str(file).replace("../", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
(destination / "dependencies.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
