"""Load the attack corpus from YAML files in corpus/.

Attacks are data, not code: each YAML file holds one attack *family* and a
list of attacks. The loader flattens them into Attack records and validates
as it goes, so a typo (duplicate id, empty prompt) fails loudly instead of
quietly corrupting every ASR number downstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Attack:
    id: str
    family: str
    technique: str
    prompt: str


def load_corpus(corpus_dir: str | Path = "corpus") -> list[Attack]:
    corpus_dir = Path(corpus_dir)
    attacks: list[Attack] = []
    seen_ids: set[str] = set()

    for path in sorted(corpus_dir.glob("*.yaml")):
        # safe_load, never load: never build arbitrary Python objects from YAML.
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        family = doc["family"]
        for item in doc["attacks"]:
            aid = item["id"]
            if aid in seen_ids:
                raise ValueError(f"Duplicate attack id {aid!r} (in {path.name})")
            seen_ids.add(aid)

            prompt = (item.get("prompt") or "").strip()
            if not prompt:
                raise ValueError(f"Empty prompt for attack {aid!r} in {path.name}")

            attacks.append(
                Attack(
                    id=aid,
                    family=family,
                    technique=item.get("technique", ""),
                    prompt=prompt,
                )
            )

    if not attacks:
        raise ValueError(f"No attacks found in {corpus_dir}/ (expected *.yaml files)")
    return attacks
