#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tqdm import tqdm


sys.path.append(str(Path(__file__).resolve().parent.parent))
from common.params import BioELXParser



def iter_wikidata_records(jsonl_path: str):
    """Yield (cui, name) tuples from a UMLS-Wikidata JSONL file.

    Each record looks like:
        {"qid": "...", "label": "...", "cui": ["C..."], "aliases": [...]}
    A record may map to multiple CUIs; for each CUI we emit one line for
    the label and one line per alias.
    """
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc=f"Reading {os.path.basename(jsonl_path)}"):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cuis = rec.get("cui") or []
            label = rec.get("label") or ""
            aliases = rec.get("aliases") or []

            names = []
            if label:
                names.append(label)
            names.extend(a for a in aliases if a)

            for cui in cuis:
                if not cui:
                    continue
                for name in names:
                    yield cui, name


def main(params):
    kb_path = params["kb_path"]
    output_path = params["output_path"]
    lowercase = bool(params["lowercase"])
    dedup = bool(params["dedup"])

    if not os.path.isfile(kb_path):
        raise FileNotFoundError(f"JSONL file not found: {kb_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    seen: set[tuple[str, str]] = set()
    written = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for cui, name in iter_wikidata_records(kb_path):
            if lowercase:
                name = name.lower()
            if dedup:
                key = (cui, name)
                if key in seen:
                    continue
                seen.add(key)
            out.write(f"{cui}||{name}\n")
            written += 1

    print(f"Wrote {written} lines to {output_path} (lowercase={lowercase}, dedup={dedup})")


if __name__ == "__main__":
    parser = BioELXParser(add_bioelx_args=True, description="Convert UMLS-Wikidata JSONL to xl-bel (CUI||name) format.")
    parser.add_kb_processing_args()
    args = parser.parse_args()
    main(vars(args))
