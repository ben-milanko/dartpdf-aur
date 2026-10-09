"""Check a signed stable-channel Snap in a disposable Ubuntu 22.04 job."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def checked(command):
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}")
    return result.stdout


def main():
    assert os.geteuid() != 0, "Desktop-user test must not run as root"
    print("Desktop test UID:", os.geteuid())
    print("Desktop test cgroup:", Path("/proc/self/cgroup").read_text().strip())
    checked(["systemctl", "--user", "is-active", "dbus.socket"])
    checked(["busctl", "--user", "status", "org.freedesktop.systemd1"])
    fixture = Path.home() / "snap/dartpdf/common/public sample.pdf"
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == (
        "fcee6184c0d776126782cd2799797b106373278c8ea0a4354ee4e33cd8663d51"
    )
    version = json.loads(Path(
        "/snap/dartpdf/current/data/flutter_assets/version.json"
    ).read_text())
    assert version["version"] == "8.0.0", version
    print("Published GUI bundle identity:", json.dumps(version))
    cli = checked(["snap", "run", "dartpdf.cli", "--version"])
    assert cli.startswith("dartpdf "), cli
    print("CLI protocol version is separate from the app release version.")
    inspection = json.loads(checked([
        "snap", "run", "dartpdf.cli", "inspect", str(fixture), "--json"
    ]))
    assert inspection["schemaVersion"] == 1, inspection
    assert inspection["pageCount"] == 1, inspection

    log_path = fixture.parent / "gui-validation.log"
    fatal = re.compile(
        r"Gtk-CRITICAL|GLib-GObject-CRITICAL|Atk-CRITICAL|AccessDenied|GTK_IS_WIDGET|"
        r"GLIBC_[\d.]+.*not found|error while loading shared libraries"
    )
    with log_path.open("w") as log:
        gui = subprocess.Popen(
            ["snap", "run", "dartpdf", str(fixture)],
            stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"},
        )
        started = time.monotonic()
        mapped_at = None
        try:
            while time.monotonic() - started < 30:
                if gui.poll() is not None:
                    raise RuntimeError(f"GUI exited during launch: {gui.returncode}")
                if fatal.search(log_path.read_text()):
                    raise RuntimeError("Critical GTK, D-Bus or loader error")
                windows = checked(["xwininfo", "-root", "-tree"])
                if "DartPDF" in windows or "dev.milanko.dartpdf" in windows:
                    mapped_at = time.monotonic()
                    print(f"DartPDF window mapped after {mapped_at - started:.2f}s")
                    break
                time.sleep(1)
            assert mapped_at is not None, "No DartPDF window within 30 seconds"
            profile = Path(f"/proc/{gui.pid}/attr/current").read_text().strip()
            print("Actual GUI AppArmor profile:", profile)
            assert profile == "snap.dartpdf.dartpdf (enforce)", profile
            print("Actual GUI cgroup:", Path(f"/proc/{gui.pid}/cgroup").read_text().strip())
            while time.monotonic() - mapped_at < 10:
                time.sleep(1)
                assert gui.poll() is None, "GUI exited after mapping its window"
                assert not fatal.search(log_path.read_text()), "Fatal launch diagnostic"
            print("PASS: signed published Snap, normal desktop user, enforced "
                  "GUI AppArmor profile, app identity, "
                  "CLI inspection and mapped GUI surviving ten seconds. "
                  "This is not a visual or all-feature editing certification.")
        finally:
            gui.terminate()
            try:
                gui.wait(timeout=5)
            except subprocess.TimeoutExpired:
                gui.kill()
                gui.wait(timeout=5)
            print(log_path.read_text()[-16000:])


if __name__ == "__main__":
    main()
