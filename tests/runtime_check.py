import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def checked(command):
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command[0]}")
    return result.stdout


asset_version = json.loads(Path(
    "/opt/dartpdf/data/flutter_assets/version.json").read_text())
assert asset_version["version"] == "8.0.0", asset_version
print("GUI bundle version:", asset_version["version"])
cli_version = checked(["/usr/bin/dartpdf-cli", "--version"])
assert cli_version.startswith("dartpdf "), cli_version
print("CLI protocol version is separate from the GUI release version.")
assert hashlib.sha256(Path("/tmp/dartpdf-aur-test/empty.pdf").read_bytes()).hexdigest() == (
    "fcee6184c0d776126782cd2799797b106373278c8ea0a4354ee4e33cd8663d51")
inspection = json.loads(checked([
    "/usr/bin/dartpdf-cli", "inspect", "/tmp/dartpdf-aur-test/empty.pdf", "--json"
]))
assert inspection["schemaVersion"] == 1, inspection
assert inspection["pageCount"] == 1, inspection

log_path = Path("/tmp/dartpdf-aur-test/gui.log")
with log_path.open("w") as log:
    gui = subprocess.Popen(
        ["/usr/bin/dartpdf"], stdout=log, stderr=subprocess.STDOUT,
        env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"})
    visible = False
    try:
        for _ in range(30):
            if gui.poll() is not None:
                raise RuntimeError(f"GUI exited during launch: {gui.returncode}")
            windows = subprocess.run(
                ["xwininfo", "-root", "-tree"], text=True,
                capture_output=True, timeout=5).stdout
            if '"DartPDF"' in windows:
                visible = True
                print("DartPDF X11 window:", windows)
                break
            time.sleep(1)
        assert visible, "No DartPDF window appeared within 30 seconds"
        time.sleep(2)
        assert gui.poll() is None, "GUI exited immediately after mapping its window"
    finally:
        gui.terminate()
        try:
            gui.wait(timeout=5)
        except subprocess.TimeoutExpired:
            gui.kill()
            gui.wait(timeout=5)
        print(log_path.read_text()[-12000:])
print("PASS: GUI bundle, CLI inspection and mapped-window smoke checks")
