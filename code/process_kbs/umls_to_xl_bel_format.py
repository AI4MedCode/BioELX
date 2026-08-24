#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path

from tqdm import tqdm


sys.path.append(str(Path(__file__).resolve().parent.parent))
from common.params import BioELXParser



def iter_mrconso_records(mrconso_path: str):
    """Yield (cui, name) tuples from MRCONSO.RRF."""
    with open(mrconso_path, "r", encoding="utf-8", errors="replace") as f:
        for line in tqdm(f, desc=f"Reading {os.path.basename(mrconso_path)}"):
            parts = line.rstrip("\n").split("|")
            if len(parts) < 15:
                continue
            cui = parts[0]
            name = parts[14]
            if not cui or not name:
                continue
            yield cui, name


def main(params):
    kb_path = params["kb_path"]
    output_path = params["output_path"]
    lowercase = bool(params["lowercase"])
    dedup = bool(params["dedup"])

    if not os.path.isfile(kb_path):
        raise FileNotFoundError(f"MRCONSO file not found: {kb_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    seen: set[tuple[str, str]] = set()
    written = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for cui, name in iter_mrconso_records(kb_path):
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
    parser = BioELXParser(add_bioelx_args=True, description="Convert UMLS MRCONSO.RRF to xl-bel (CUI||name) format.")
    parser.add_kb_processing_args()
    args = parser.parse_args()
    main(vars(args))
