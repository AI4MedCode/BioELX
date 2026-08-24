#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

sys.path.append(str(Path(__file__).resolve().parent.parent))
from common.constants import DATA_DIR
from common.params import BioELXParser


def insert_tgt(text: str, start: int, end: int) -> str:
    """Wrap text[start:end] in <tgt>...</tgt>."""
    if start < 0 or end > len(text) or start >= end:
        return text
    return text[:start] + "<tgt>" + text[start:end] + "</tgt>" + text[end:]


def insert_tgt_multi(text: str, spans):
    """
    Insert <tgt></tgt> for possibly multiple spans.
    Insert from right to left so offsets remain valid.
    """
    spans_sorted = sorted(spans, key=lambda x: x[0], reverse=True)
    t = text
    for s, e in spans_sorted:
        if s < 0 or e > len(t) or s >= e:
            continue
        t = t[:s] + "<tgt>" + t[s:e] + "</tgt>" + t[e:]
    return t


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_lines(out_path: Path, lines):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    return out_path, len(lines)


def keep_split(name: str, splits) -> bool:
    """True if `name` was requested (splits=None means keep everything)."""
    return splits is None or name in splits


# ---------------------------------------------------------------------- mantra

def parse_ann_lines(ann_text: str):
    """
    Parse BRAT .ann lines like:
      T1\tC1721214 13 21\tPROTELOS
      T3\tC0546837 44 53;60 69\tOSOPHAGUS KARZINOME   (discontinuous spans)
    Return list of (cui, spans[(start,end)...], mention_text)
    """
    out = []
    for line in ann_text.splitlines():
        if not line.startswith("T"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        meta = parts[1].strip().split()
        if len(meta) < 3:
            continue

        cui = meta[0]
        mention = parts[2].strip()

        span_str = " ".join(meta[1:])  # e.g. "44 53;60 69"
        spans = []
        for seg in span_str.split(";"):
            seg = seg.strip()
            if not seg:
                continue
            nums = seg.split()
            if len(nums) >= 2:
                try:
                    s = int(nums[0])
                    e = int(nums[1])
                    spans.append((s, e))
                except ValueError:
                    pass

        if spans:
            out.append((cui, spans, mention))
    return out


def dataset_bucket(ds_name: str):
    """
    Map Mantra subfolder name -> bucket
    Examples seen:
      EMEA_ec22-cui-best_man -> EMEA
      Medline_EN_DE_ec22...  -> Medline
      Patents_ec22...        -> Patent
    """
    low = ds_name.lower()
    if low.startswith("emea"):
        return "EMEA"
    if low.startswith("medline"):
        return "Medline"
    if low.startswith("patent") or low.startswith("patents"):
        return "Patent"
    return None


def convert_mantra(data_path: Path, out_root: Path, splits=None):
    """Mantra-GSC zip -> <out_root>/<bucket>/<lang>.txt. `splits` filters buckets."""
    if data_path.is_dir():
        data_path = data_path / "Mantra-GSC-XML.zip"
    if not data_path.is_file():
        raise FileNotFoundError(f"Mantra zip not found: {data_path}")

    # bucket -> lang -> list of lines
    bucket_lang_lines = defaultdict(lambda: defaultdict(list))

    with zipfile.ZipFile(data_path, "r") as z:
        names = z.namelist()
        name_set = set(names)

        for n in names:
            if not n.startswith("Mantra-GSC/"):
                continue
            if n.startswith("__MACOSX/") or "/__MACOSX" in n:
                continue

            p = PurePosixPath(n)

            # Expect: Mantra-GSC/<Lang>/<Dataset>/<file>.ann
            if p.suffix != ".ann" or len(p.parts) < 4:
                continue

            lang = p.parts[1]
            ds_folder = p.parts[2]
            bucket = dataset_bucket(ds_folder)
            if bucket is None or not keep_split(bucket, splits):
                continue

            txt_path = str(p.with_suffix(".txt"))
            if txt_path not in name_set:
                continue

            ann_text = z.read(n).decode("utf-8", errors="replace")
            txt_text = z.read(txt_path).decode("utf-8", errors="replace")

            for cui, spans, mention in parse_ann_lines(ann_text):
                marked = normalize_newlines(insert_tgt_multi(txt_text, spans))
                bucket_lang_lines[bucket][lang].append(f"{cui}||{mention}||{marked}")

    written = []
    for bucket, lang_map in sorted(bucket_lang_lines.items()):
        for lang, lines in sorted(lang_map.items()):
            written.append(write_lines(out_root / bucket / f"{lang}.txt", lines))
    return written


# ----------------------------------------------------------------- medmentions

MEDMENTIONS_PMID_FILES = {
    "train": "corpus_pubtator_pmids_trng.txt",
    "dev": "corpus_pubtator_pmids_dev.txt",
    "test": "corpus_pubtator_pmids_test.txt",
}


def parse_pubtator(corpus_path: str):
    """Parse a MedMentions PubTator file into [{pmid, text, anns}] entries.

    Document layout (blank-line separated):
        <pmid>|t|<title>
        <pmid>|a|<abstract>
        <pmid>\t<start>\t<end>\t<mention>\t<sem_type>\t<UMLS:Cxxx>
        ...

    text = title + " " + abstract  (PubTator convention; offsets refer to it)
    anns = list of (cui, start, end, mention)
    """
    docs = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        raw = normalize_newlines(f.read())

    for block in raw.split("\n\n"):
        block = block.strip("\n")
        if not block:
            continue
        lines = block.split("\n")
        pmid = None
        title = ""
        abstract = ""
        anns = []
        for line in lines:
            if "|t|" in line and not line.startswith("\t"):
                pmid, _, title = line.partition("|t|")
            elif "|a|" in line and not line.startswith("\t"):
                _, _, abstract = line.partition("|a|")
            else:
                parts = line.split("\t")
                if len(parts) >= 6:
                    try:
                        s = int(parts[1])
                        e = int(parts[2])
                    except ValueError:
                        continue
                    mention = parts[3]
                    cui = parts[5]
                    if cui.startswith("UMLS:"):
                        cui = cui[len("UMLS:"):]
                    anns.append((cui, s, e, mention))
        if pmid:
            text = title + " " + abstract
            docs.append({"pmid": pmid, "text": text, "anns": anns})
    return docs


def load_pmid_set(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def convert_medmentions(data_path: Path, out_root: Path, splits=None):
    """MedMentions PubTator -> <out_root>/<split>.txt, split by pmid lists."""
    src_dir = data_path if data_path.is_dir() else data_path.parent
    corpus_path = data_path if data_path.is_file() else src_dir / "corpus_pubtator.txt"
    if not corpus_path.is_file():
        raise FileNotFoundError(f"MedMentions corpus not found: {corpus_path}")

    split_paths = {
        name: src_dir / fname
        for name, fname in MEDMENTIONS_PMID_FILES.items()
        if keep_split(name, splits)
    }
    for name, path in split_paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"pmid list for split '{name}' not found: {path}")

    docs = parse_pubtator(str(corpus_path))
    split_pmids = {name: load_pmid_set(str(p)) for name, p in split_paths.items()}

    split_lines = {name: [] for name in split_paths}
    for doc in docs:
        text = normalize_newlines(doc["text"])
        for cui, s, e, mention in doc["anns"]:
            if not cui or not mention:
                continue
            line = f"{cui}||{mention}||{insert_tgt(text, s, e)}"
            for name, pmids in split_pmids.items():
                if doc["pmid"] in pmids:
                    split_lines[name].append(line)
                    break

    return [write_lines(out_root / f"{name}.txt", lines)
            for name, lines in split_lines.items()]


# ------------------------------------------------------------------ wikimed-de

_SENT_BOUNDARY = {".", "!", "?", "\n"}


def sentence_with_tgt(text: str, start: int, end: int) -> str:
    """Return the single sentence containing text[start:end], with the
    mention wrapped in <tgt>...</tgt>. Sentence boundaries are '.', '!',
    '?', or newline."""
    if start < 0 or end > len(text) or start >= end:
        return ""

    # nearest sentence boundary strictly before `start`
    s = 0
    for i in range(start - 1, -1, -1):
        if text[i] in _SENT_BOUNDARY:
            s = i + 1
            break

    # nearest sentence boundary at or after `end` (include the punctuation)
    e = len(text)
    for i in range(end, len(text)):
        if text[i] in _SENT_BOUNDARY:
            e = i + 1
            break

    sentence = text[s:start] + "<tgt>" + text[start:end] + "</tgt>" + text[end:e]
    return sentence.strip()


def doc_mentions_to_xlbel(text: str, mentions):
    """Yield 'cui||mention||sentence_with_<tgt>' lines for each mention."""
    text = normalize_newlines(text)
    for m in mentions:
        cui = m.get("cui")
        mention = m.get("mention")
        start = m.get("start_index")
        end = m.get("end_index")
        if not cui or not mention or start is None or end is None:
            continue
        sentence = sentence_with_tgt(text, start, end)
        if not sentence:
            continue
        yield f"{cui}||{mention}||{sentence}"


def convert_wikimed_de(data_path: Path, out_root: Path, splits=None):
    """WikiMed-DE <split>_data_bel.json -> <out_root>/<split>.txt."""
    if splits is None:
        splits = ["test"]

    src_dir = data_path if data_path.is_dir() else data_path.parent
    written = []
    for split in splits:
        json_path = data_path if data_path.is_file() else src_dir / f"{split}_data_bel.json"
        if not json_path.is_file():
            raise FileNotFoundError(f"WikiMed-DE json for split '{split}' not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        lines = []
        for doc in docs:
            lines.extend(doc_mentions_to_xlbel(doc.get("text", ""), doc.get("mentions", [])))
        written.append(write_lines(out_root / f"{split}.txt", lines))
    return written


# -------------------------------------------------------------------- dispatch

# dataset name -> (converter, default sub-dir under DATA_DIR)
DATASETS = {
    "mantra": (convert_mantra, "mantra"),
    "medmentions": (convert_medmentions, "medmentions"),
    "wikimed-de": (convert_wikimed_de, "wikimed_de"),
}


def main(params):
    dataset = params["dataset"]
    convert, sub_dir = DATASETS[dataset]

    data_path = Path(params["data_path"] or os.path.join(DATA_DIR, sub_dir))
    if not data_path.exists():
        raise FileNotFoundError(f"input path not found: {data_path}")

    default_out = (data_path if data_path.is_dir() else data_path.parent) / "processed"
    out_root = Path(params["output_path"] or default_out)
    out_root.mkdir(parents=True, exist_ok=True)

    splits = params["splits"]
    print(f"[config] dataset={dataset}")
    print(f"[config] data_path={data_path}")
    print(f"[config] output_path={out_root}")
    print(f"[config] splits={splits or 'all'}")

    written = convert(data_path, out_root, splits)

    print("Wrote:")
    for path, n in written:
        print(f"  {path} ({n} lines)")


if __name__ == "__main__":
    parser = BioELXParser(
        add_bioelx_args=True,
        description="Convert annotated corpora (Mantra-GSC, MedMentions, WikiMed-DE) to xl-bel mention format.",
    )
    parser.add_dataset_processing_args()
    args = parser.parse_args()
    main(vars(args))
