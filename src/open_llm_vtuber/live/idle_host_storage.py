"""Small atomic JSON files shared by local hosting components."""

import json
import os
import tempfile
import time
from pathlib import Path


def read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Electron/OBS can briefly hold the destination open on Windows. Distinct
    # temporary files also avoid collisions between independently running hosts.
    descriptor, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False)
        for attempt in range(6):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(.005 * 2**attempt)
    finally:
        temporary.unlink(missing_ok=True)
