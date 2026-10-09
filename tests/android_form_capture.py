"""Capture the actual signed Android release using the official SDK.

Fresh disposable AVD, stock initialization, enforced SELinux, no root,
security bypass, new license acceptance, app rebuild or image retouching.
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


PACKAGE = "dev.milanko.dartpdf"
COMPONENT = PACKAGE + "/dev.milanko.dart_pdf_editor_app.MainActivity"
IMAGE = "system-images;android-35;google_apis;x86_64"
NAME = "dartpdf-published-form"
SERIAL = "emulator-5554"


def checked(command, *, timeout=60, env=None, input_text=None):
    print("COMMAND:", json.dumps([str(value) for value in command]), flush=True)
    result = subprocess.run(command, input=input_text, stdin=(
        subprocess.DEVNULL if input_text is None else None
    ), text=True, capture_output=True, timeout=timeout, env=env)
    print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", flush=True)
    if result.returncode:
        raise RuntimeError(f"Command exited {result.returncode}")
    return result.stdout


def emit_png(data, name, scope):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "Native screenshot is not PNG"
    width, height = struct.unpack(">II", data[16:24])
    assert len(data) < 3 * 1024 * 1024, "Bounded log transfer exceeded"
    proof = {"name": name, "width": width, "height": height,
             "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
             "scope": scope, "visualReviewRequired": True}
    print("DARTPDF_ANDROID_CAPTURE_BEGIN " + json.dumps(proof), flush=True)
    encoded = base64.b64encode(data).decode("ascii")
    for offset in range(0, len(encoded), 1024):
        print("DARTPDF_ANDROID_CAPTURE_PNG " + encoded[offset:offset + 1024])
    print("DARTPDF_ANDROID_CAPTURE_END " + proof["sha256"], flush=True)


def main():
    sdk = Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ["ANDROID_HOME"])
    temp = Path(os.environ["RUNNER_TEMP"])
    apk = temp / "dartpdf-app-release.apk"
    fixture = Path("tests/fixtures/muster-ausleihformular.pdf")
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == (
        "68580d92b005b53ba979b4bfa6c9445d03d6d484c79af45f09803f2951082eca"
    )
    print("Host UID:", os.geteuid())
    print("Host disk available bytes:", os.statvfs(temp).f_bavail * os.statvfs(temp).f_frsize)
    assert os.statvfs(temp).f_bavail * os.statvfs(temp).f_frsize > 8 * 1024**3
    print("Existing KVM read/write access:", os.access("/dev/kvm", os.R_OK | os.W_OK))
    print("Explicit software emulation; unsupported/slow SDK mode, no KVM permission change")
    build = sdk / "build-tools/35.0.0"
    badging = checked([str(build / "aapt"), "dump", "badging", str(apk)])
    assert "name='dev.milanko.dartpdf' versionCode='44' versionName='8.0.0'" in badging
    assert "'x86_64'" in badging, "Published APK lacks guest ABI"
    signature = checked([str(build / "apksigner"), "verify", "--print-certs", str(apk)])
    assert "4fbf4e9da8c7d2b1e7c3bee006aefbf8b8faa99f610ac0877e3e88d6d6fa6140" in signature

    sdkmanager = sdk / "cmdline-tools/latest/bin/sdkmanager"
    avdmanager = sdk / "cmdline-tools/latest/bin/avdmanager"
    java_env = {**os.environ, "JAVA_HOME": os.environ["JAVA_HOME_17_X64"]}
    # No --licenses, yes pipe or interactive agreement acceptance.
    checked([str(sdkmanager), "emulator", IMAGE], timeout=480, env=java_env)
    system = sdk / "system-images/android-35/google_apis/x86_64/system.img"
    assert system.is_file() and system.stat().st_size > 10 * 1024**2
    avd = temp / (NAME + ".avd")
    assert not avd.exists(), "Disposable AVD target already exists"
    checked([str(avdmanager), "create", "avd", "--name", NAME,
             "--package", IMAGE, "--device", "pixel_3a", "--path", str(avd)],
            env=java_env, input_text="no\n")
    emulator = sdk / "emulator/emulator"
    checked([str(emulator), "-version"])
    checked([str(emulator), "-help-accel"])
    adb = str(sdk / "platform-tools/adb")

    def device(*arguments, timeout=60):
        return checked([adb, "-s", SERIAL, *arguments], timeout=timeout)

    log_path = temp / "dartpdf-owned-emulator.log"
    booted = False
    with log_path.open("w") as log:
        process = subprocess.Popen([
            str(emulator), "@" + NAME, "-port", "5554", "-no-window",
            "-no-snapshot", "-no-audio", "-no-boot-anim", "-accel", "off",
            "-gpu", "swiftshader_indirect", "-memory", "2048", "-cores", "1",
        ], stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "ANDROID_I_WANT_MY_TCG": "yes"})
        try:
            checked([adb, "start-server"])
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                assert process.poll() is None, "Owned emulator exited before boot"
                readback = subprocess.run(
                    [adb, "-s", SERIAL, "shell", "getprop", "sys.boot_completed"],
                    text=True, capture_output=True, timeout=30,
                )
                if readback.returncode == 0 and readback.stdout.strip() == "1":
                    booted = True
                    break
                time.sleep(5)
            assert booted, "No completed software-emulation boot within ten minutes"
            print("Actual boot completed; stock SDK-created data, no -initdata argument")
            device("shell", "getprop", "ro.build.version.sdk")
            device("shell", "getprop", "ro.product.cpu.abi")
            assert "Enforcing" in device("shell", "getenforce")
            device("install", "--no-streaming", str(apk), timeout=120)
            installed = device("shell", "dumpsys", "package", PACKAGE)
            assert "versionName=8.0.0" in installed and "versionCode=44" in installed
            help_text = device("shell", "cmd", "locale", "help")
            assert "set-app-locales" in help_text and "get-app-locales" in help_text
            device("shell", "cmd", "locale", "set-app-locales", PACKAGE,
                   "--user", "0", "--locales", "de-DE")
            assert "de-DE" in device("shell", "cmd", "locale", "get-app-locales", PACKAGE, "--user", "0")
            device("push", str(fixture), "/sdcard/Download/muster-ausleihformular.pdf")
            device("shell", "input", "keyevent", "82")
            uri = ("content://com.android.externalstorage.documents/document/"
                   "primary%3ADownload%2Fmuster-ausleihformular.pdf")
            device("shell", "am", "start", "--grant-read-uri-permission", "-a",
                   "android.intent.action.VIEW", "-t", "application/pdf", "-d", uri,
                   "-n", COMPONENT)
            time.sleep(20)
            pid = device("shell", "pidof", PACKAGE).strip()
            assert re.fullmatch(r"\d+", pid), "Published app not running"
            focus = device("shell", "dumpsys", "window", "windows")
            assert re.search(r"mCurrentFocus=.*dev\.milanko\.dartpdf", focus), "App is not the focused window"
            try:
                device("shell", "uiautomator", "dump", "/sdcard/dartpdf-capture-ui.xml", timeout=30)
                xml = device("exec-out", "cat", "/sdcard/dartpdf-capture-ui.xml")
                print("DARTPDF_ANDROID_NATIVE_UI " + json.dumps({"xml": xml}, ensure_ascii=False))
            except Exception as error:
                print("Native UI hierarchy unavailable:", str(error))
            screenshot = subprocess.run([adb, "-s", SERIAL, "exec-out", "screencap", "-p"],
                                        capture_output=True, timeout=30, check=True).stdout
            emit_png(screenshot, "android8-de-form-raw.png",
                     "Actual signed APK8.0.0+44 on isolated Android35 using unsupported software emulation; "
                     "requested per-app German locale. No performance/hardware-acceleration claim. "
                     "Focused app and native pixels require visual document/language review. "
                     "Prefilled fictional form; no save/edit/signature or Play-signed compatibility proof.")
            device("logcat", "-d", "--pid=" + pid, "*:W", timeout=30)
            print("PASS: actual release install, focused app and native screenshot; visual review still required")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            print("Owned emulator terminal exit:", process.returncode)
            # Avoid publishing automatically generated emulator/ADB auth material.
            lines = log_path.read_text(errors="replace").splitlines()[-150:]
            safe = [line for line in lines if not re.search(r"key|token|authorization", line, re.I)]
            print("Emulator diagnostic tail:\n" + "\n".join(safe))


if __name__ == "__main__":
    main()
