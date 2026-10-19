"""Sync Mao's one Markdown persona without changing voice or model settings."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PERSONA_PATH = Path("prompts/mao_context.vi.md")
PERSONA_MARKER = "MAO_FEM_MALFOY_V1"


class LiteralDumper(yaml.SafeDumper):
    pass


LiteralDumper.add_representer(
    str,
    lambda dumper, text: dumper.represent_scalar(
        "tag:yaml.org,2002:str", text, style="|" if "\n" in text else None
    ),
)


def main():
    persona = (ROOT / PERSONA_PATH).read_text(encoding="utf-8")
    if PERSONA_MARKER not in persona or not persona.strip():
        raise ValueError("Mao's Markdown persona is missing its identity marker")
    paths = ["conf.yaml", "characters/mao_live.yaml"]
    for relative in paths:
        path = ROOT / relative
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        character = config["character_config"]
        character.update(
            persona_prompt=persona,
            conf_name="Mao VTuber — Fem Malfoy",
            conf_uid="mao_fem_malfoy_vi_003",
            character_name="Mao",
        )
        path.write_text(
            yaml.dump(
                config, Dumper=LiteralDumper, allow_unicode=True, sort_keys=False
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
