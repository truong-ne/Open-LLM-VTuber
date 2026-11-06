"""Apply the operator-reviewed LIVE profile without resetting other profile fields."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from scripts.mao_profile import load_profile, save_profile
    from src.open_llm_vtuber.agent.hybrid.persona import ProfileEdit
    from src.open_llm_vtuber.live.idle_host_storage import read_json, write_json

    settings_path = ROOT / "private/mao-idle-host.json"
    settings = read_json(settings_path)
    settings.update(share_min_turns=3, share_quiet_seconds=60, require_desktop=True)
    write_json(settings_path, settings)
    profile = load_profile()
    changes = json.loads(
        (ROOT / "knowledge/mao-live-persona.vi.json").read_text(encoding="utf-8")
    )
    if all(profile.get(key) == value for key, value in changes.items()):
        print("LIVE profile already current:", profile["revision"])
        return
    backup = (
        ROOT / f"private/mao-profile-before-live-review-r{profile['revision']}.json"
    )
    backup.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    profile.update(changes)
    result = save_profile({key: profile[key] for key in ProfileEdit.model_fields})
    print("LIVE profile applied:", result["revision"])


if __name__ == "__main__":
    main()
