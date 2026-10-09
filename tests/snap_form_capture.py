"""Capture genuine published Snap pixels with an existing fictional PDF.

No app rebuild, marketing overlay, PDF edit, signing or security workaround.
PNG bytes are returned in the ordinary job log, not charged artifact storage.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import time

from snap_runtime_check import checked


FATAL = re.compile(
    r"Gtk-CRITICAL|GLib-GObject-CRITICAL|Atk-CRITICAL|AccessDenied|GTK_IS_WIDGET|"
    r"GLIBC_[\d.]+.*not found|error while loading shared libraries"
)


def main():
    assert os.geteuid() != 0, "Normal-user capture must not run as root"
    print("Capture UID:", os.geteuid())
    checked(["systemctl", "--user", "is-active", "dbus.socket"])
    checked(["busctl", "--user", "status", "org.freedesktop.systemd1"])
    checked(["busctl", "--user", "call", "org.a11y.Bus", "/org/a11y/bus",
             "org.a11y.Bus", "GetAddress"])
    checked(["busctl", "--user", "status", "org.a11y.Bus"])
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    desktop = Atspi.get_desktop(0)
    assert desktop is not None

    form = Path.home() / "snap/dartpdf/common/Equipment loan form.pdf"
    assert hashlib.sha256(form.read_bytes()).hexdigest() == (
        "48cd26eab84e705b01b3c7e1c4a86d763ec277809258885a4196ae3234efbf9d"
    )
    version = json.loads(Path(
        "/snap/dartpdf/current/data/flutter_assets/version.json"
    ).read_text())
    assert version["version"] == "8.0.0" and version["build_number"] == "44", version
    print("Published bundle identity:", json.dumps(version))
    print("Signed installed revision:", Path("/snap/dartpdf/current").resolve().name)
    inspection = json.loads(checked([
        "snap", "run", "dartpdf.cli", "inspect", str(form), "--json"
    ]))
    assert inspection["pageCount"] == 1, inspection
    assert inspection["forms"]["present"], inspection
    assert inspection["forms"]["fieldCount"] == 6, inspection

    log_path = form.parent / "form-capture-gui.log"
    with log_path.open("w") as log:
        gui = subprocess.Popen(
            ["snap", "run", "dartpdf", str(form)],
            stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"},
        )
        try:
            started = time.monotonic()
            window = None
            while time.monotonic() - started < 30:
                assert gui.poll() is None, "Published GUI exited during launch"
                assert not FATAL.search(log_path.read_text()), "Fatal native diagnostic"
                windows = checked(["xwininfo", "-root", "-tree"])
                found = re.search(r'^\s*(0x[\da-fA-F]+)\s+"DartPDF":', windows, re.M)
                if found:
                    window = found.group(1)
                    break
                time.sleep(1)
            assert window is not None, "No actual DartPDF window"
            profile = Path(f"/proc/{gui.pid}/attr/current").read_text().strip()
            assert profile == "snap.dartpdf.dartpdf (enforce)", profile
            print("Actual GUI AppArmor profile:", profile)
            print("Actual GUI cgroup:", Path(f"/proc/{gui.pid}/cgroup").read_text().strip())

            # Resize the real X window, not its pixels or a synthetic app frame.
            checked(["xdotool", "windowsize", window, "1440", "1100"])
            accessible = None
            for _ in range(10):
                desktop.clear_cache()
                for index in range(desktop.get_child_count()):
                    app = desktop.get_child_at_index(index)
                    if app is not None and app.get_process_id() == gui.pid:
                        accessible = {"pid": app.get_process_id(), "name": app.get_name(),
                                      "children": app.get_child_count()}
                        break
                assert gui.poll() is None, "GUI exited while waiting for native capture"
                assert not FATAL.search(log_path.read_text()), "Fatal native diagnostic"
                time.sleep(1)
            assert accessible is not None and accessible["children"] > 0, accessible
            print("Actual accessible application:", json.dumps(accessible))
            checked(["xwininfo", "-id", window])

            output = form.parent / "linux-snap8-form-raw.png"
            checked(["import", "-window", window, str(output)])
            data = output.read_bytes()
            assert data[:8] == b"\x89PNG\r\n\x1a\n", "Capture is not PNG"
            width, height = struct.unpack(">II", data[16:24])
            assert (width, height) == (1440, 1100), (width, height)
            assert len(data) < 2 * 1024 * 1024, "Bounded job-log transfer exceeded"
            assert gui.poll() is None and not FATAL.search(log_path.read_text())
            proof = {"name": output.name, "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest(),
                     "width": width, "height": height, "windowId": window,
                     "source": "Real published confined normal-user Linux Snap window",
                     "prefilledFixtureNotAppEditingProof": True,
                     "visualReviewRequired": True}
            print("DARTPDF_CAPTURE_BEGIN " + json.dumps(proof))
            encoded = base64.b64encode(data).decode("ascii")
            for offset in range(0, len(encoded), 1024):
                print("DARTPDF_CAPTURE_PNG " + encoded[offset:offset + 1024])
            print("DARTPDF_CAPTURE_END " + proof["sha256"])
            print("PASS: genuine window capture and bounded log transfer; "
                  "not a save/edit/signature, complete desktop or store-conversion test.")
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
