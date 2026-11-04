"""Load the attack corpus and print a summary grouped by family.

This verifies the YAML parses and ids are unique *before* we spend time
running anything against a model.

    python -m scripts.list_corpus
"""
from __future__ import annotations

from collections import Counter

from backend.corpus import load_corpus


def main() -> None:
    attacks = load_corpus()
    by_family = Counter(a.family for a in attacks)

    print(f"Loaded {len(attacks)} attacks across {len(by_family)} families:\n")
    for family, n in sorted(by_family.items()):
        print(f"  {family:16s} {n:3d}")

    print("\nSample attacks:")
    for a in attacks[:3]:
        preview = a.prompt.replace("\n", " ")[:68]
        print(f"  [{a.id}] {a.technique:20s} {preview}...")


if __name__ == "__main__":
    main()
