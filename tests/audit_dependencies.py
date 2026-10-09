import json
from pathlib import Path
import re
import subprocess


bundle = Path("/usr/lib/dartpdf")
providers = set()
missing = {}
objects = [bundle / "dart_pdf_editor_app", bundle / "dartpdf-cli", *sorted((bundle / "lib").glob("*.so*"))]
for obj in objects:
    dynamic = subprocess.run(["readelf", "-d", str(obj)], text=True,
                             capture_output=True, check=True).stdout
    needed = re.findall(r"\(NEEDED\).*\[([^\]]+)\]", dynamic)
    links = subprocess.run(["ldd", str(obj)], text=True,
                           capture_output=True, check=True).stdout
    resolved = dict(re.findall(r"^\s*(\S+) => (/\S+)", links, re.MULTILINE))
    for direct in needed:
        path = resolved.get(direct)
        if path is None:
            loader = re.search(r"^\s*(/\S*/" + re.escape(direct) + r")\s", links, re.MULTILINE)
            path = loader.group(1) if loader else None
        if path is None:
            missing.setdefault(obj.name, []).append(direct)
            continue
        actual = Path(path).resolve()
        if actual.is_relative_to(bundle):
            continue
        owner = subprocess.run(["pacman", "-Qoq", str(actual)], text=True,
                               capture_output=True, check=True).stdout.strip()
        providers.update(owner.splitlines())
print("DIRECT_DEPENDENCY_AUDIT=" + json.dumps({
    "providers": sorted(providers), "unresolvedDirectLibraries": missing,
}, sort_keys=True))
