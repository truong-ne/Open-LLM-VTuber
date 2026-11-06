"""One backend-owned TikTok reader shared by the classroom and Mao room."""

from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


class ClassroomTransport:
    def __init__(self):
        self.process = None
        self.account = ""
        self.retry_at = 0

    def sync(self, enabled, account):
        if not enabled:
            self.stop()
            return
        if self.process is not None and self.process.poll() is None:
            if account == self.account:
                return
            self.stop()
        if time.monotonic() < self.retry_at:
            return
        self.retry_at = time.monotonic() + 15
        self.account = account
        with (ROOT / "logs/classroom-tiktok.log").open("ab") as log:
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    str(ROOT / "scripts/run_tiktok_live.py"),
                    "--username",
                    account,
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0,
            )

    def stop(self):
        process, self.process = self.process, None
        if process is None or process.poll() is not None:
            return
        if sys.platform == "win32":
            # The workspace venv launcher has a child interpreter on Windows.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            process.terminate()
        process.wait(timeout=10)
