"""Install a pinned official portable OBS into private/, preserving existing config."""

import hashlib
import json
from pathlib import Path
import secrets
import zipfile

import httpx

ROOT = Path(__file__).resolve().parent.parent
VERSION = "33.0.0"
DIGEST = "3369a3ecd67b5669a8a08d77357f87cc786d1fba42fbbd1054d841a69f6271a7"


def main():
    archive = ROOT / f"private/tools/OBS-Studio-{VERSION}-Windows-x64.zip"
    folder = ROOT / f"private/tools/obs-{VERSION}"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not (folder / "bin/64bit/obs64.exe").exists():
        if not archive.exists():
            url = f"https://github.com/obsproject/obs-studio/releases/download/{VERSION}/{archive.name}"
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=60
            ) as response:
                response.raise_for_status()
                with archive.open("xb") as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
        with archive.open("rb") as downloaded:
            if hashlib.file_digest(downloaded, "sha256").hexdigest() != DIGEST:
                raise ValueError(
                    "OBS archive checksum mismatch; remove this archive and retry"
                )
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                if (
                    not (folder / item.filename)
                    .resolve()
                    .is_relative_to(folder.resolve())
                ):
                    raise ValueError("Unsafe archive path")
            bundle.extractall(folder)
    (folder / "portable_mode.txt").touch()
    config = folder / "config/obs-studio"
    config.mkdir(parents=True, exist_ok=True)
    user = config / "user.ini"
    if not user.exists():
        user.write_text(
            "[General]\nFirstRun=true\nConfirmOnExit=false\n[Basic]\nProfile=Mao Local Test\nProfileDir=MaoLocalTest\n[BasicWindow]\nPreviewEnabled=true\n",
            encoding="utf-8",
        )
    profile = config / "basic/profiles/MaoLocalTest/basic.ini"
    profile.parent.mkdir(parents=True, exist_ok=True)
    if not profile.exists():
        profile.write_text(
            "[General]\nName=Mao Local Test\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSType=0\nFPSCommon=30\n[Output]\nMode=Simple\n[SimpleOutput]\nRecFormat2=mkv\nRecQuality=Small\nRecEncoder=x264\n[Audio]\nSampleRate=48000\nChannelSetup=Stereo\n",
            encoding="utf-8",
        )
    settings = config / "plugin_config/obs-websocket/config.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    if not settings.exists():
        settings.write_text(
            json.dumps(
                {
                    "first_load": False,
                    "server_enabled": False,
                    "server_port": 4457,
                    "alerts_enabled": False,
                    "auth_required": True,
                    "server_password": secrets.token_urlsafe(32),
                }
            ),
            encoding="utf-8",
        )
    print(
        "Portable OBS setup complete. Existing installation preserved; new downloads require checksum verification. No broadcast credentials."
    )


if __name__ == "__main__":
    main()
