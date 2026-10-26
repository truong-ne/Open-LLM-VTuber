"""Operator controls for Mao's idle curiosity service; never a model tool."""

import argparse
import asyncio
import json
import re
import shutil
import sys

from mao_hybrid import ROOT, config
from src.open_llm_vtuber.agent.hybrid.autonomy import AutonomyService, CONTROL, STATUS
from src.open_llm_vtuber.live.idle_host_storage import read_json, write_json


def enable():
    # Preserve YAML comments and unrelated settings; validate each edited file.
    import yaml

    for path in [ROOT / "conf.yaml", ROOT / "characters/mao_live.yaml"]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r"(?m)^( +)hybrid:\s*$", text)
        if not match:
            raise ValueError("Enable the existing hybrid configuration first")
        indent = match[1] + "  "
        tail = text[match.end() :]
        end = re.search(r"(?m)^\S|^ {0," + str(len(match[1])) + r"}\S", tail)
        stop = match.end() + end.start() if end else len(text)
        block = text[match.end() : stop]
        if re.search(r"(?m)^" + re.escape(indent) + r"autonomy:", block):
            block, count = re.subn(
                r"(?m)^("
                + re.escape(indent)
                + r"autonomy:\s*\n"
                + re.escape(indent)
                + r"  enabled:)\s*(?:true|false).*$",
                r"\1 true",
                block,
            )
            if count != 1:
                raise ValueError(
                    "Autonomy configuration must explicitly start with enabled"
                )
        else:
            block = (
                "\n"
                + indent
                + "autonomy:\n"
                + indent
                + "  enabled: true\n"
                + block.lstrip("\r\n")
            )
        updated = text[: match.end()] + block + text[stop:]
        yaml.safe_load(updated)
        backup = ROOT / "private" / (path.name + ".before-autonomy")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(updated, encoding="utf-8")
    write_json(CONTROL, {"paused": False})
    print(
        "Enabled idle curiosity. Start/restart Mao backend to load it. No stream started."
    )


async def once():
    service = AutonomyService(config())
    try:
        await service._bounded_cycle()
        print(json.dumps(read_json(STATUS), ensure_ascii=False, indent=2))
    finally:
        await service.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["enable", "pause", "resume", "status", "once"]
    )
    args = parser.parse_args()
    if args.command == "enable":
        enable()
    elif args.command in {"pause", "resume"}:
        write_json(CONTROL, {"paused": args.command == "pause"})
        print(args.command)
    elif args.command == "once":
        asyncio.run(once())
    else:
        print(json.dumps(read_json(STATUS), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
