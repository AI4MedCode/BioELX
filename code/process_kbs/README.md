# Knowledge Bases

| Knowledge base | Used for |
|---|---|
| [UMLS-399931](#umls-399931) | XL-BEL |
| [UMLS 2020AA (full release)](#notes) | EMEA, Patent, WikiMed-DE (`DE`) |
| [UMLS 2017AA (full release)](#umls) | MedMentions |
| [UMLS-Wikidata](#umls-wikidata) | WikiMed-DE (`DE-wiki`) |

## UMLS-399931
This knowledge base can be downloaded along with XL-BEL and is used to evaluate XL-BEL. It is a subset of UMLS 2020AA with 62,094 entities and 399,931 aliases, and is ready to use without any modification.

## UMLS
1. Visit **[the UMLS Knowledge Sources](https://www.nlm.nih.gov/research/umls/licensedcontent/umlsknowledgesources.html)** to download the UMLS Metathesaurus Full Subset (a UMLS license is required).
2. For older versions of UMLS, go to **[the UMLS history archive](https://www.nlm.nih.gov/research/umls/licensedcontent/umlsarchives04.html)**.

To be comparable with prior work, we use two UMLS releases:
- **UMLS 2020AA** to evaluate EMEA, Patent and WikiMed-DE (UMLS setting)
- **UMLS 2017AA** to evaluate MedMentions, which was annotated with this version

### Convert UMLS to XL-BEL Knowledge Base Format

[umls_to_xl_bel_format.py](umls_to_xl_bel_format.py) reads a UMLS `MRCONSO.RRF` file, extracts the `(CUI, name)` pair of every row (all source vocabularies and all languages), and writes one alias per line in the XL-BEL format `CUI||name`.

- Input: `META/MRCONSO.RRF`
- Output: a plain-text file with one record per line, `CUI||name` (e.g. `C0000392||beta-alanine`)
- Options:
    - `--lowercase`: lowercase every name; without it, names keep their original casing
    - `--dedup`: remove duplicated `(CUI, name)` rows; with `--lowercase`, duplicates are removed after lowercasing

```bash
python code/process_kbs/umls_to_xl_bel_format.py \
    --kb_path /path/to/umls/2020AA/META/MRCONSO.RRF \
    --output_path /path/to/save/umls2020_full.txt \
    --lowercase \
    --dedup
```

### Notes

For UMLS 2020, we reported several versions of results in the [main README](../../README.md#results). The three versions of the knowledge base are:

| Version | `MRCONSO.RRF` (input) | Processing | Processed file size | Lines (`CUI\|\|name`) | Entities (CUIs) |
|---|---|---|---|---|---|
| UMLS 2020AA Level-0 subset | ≈ 960 MB, 7,680,943 rows | English names only, original casing | 289,258,500 bytes ≈ 289 MB | 6,162,830 | 3,376,510 |
| Full UMLS 2020AA, lowercased | ≈ 1.97 GB, 15,479,756 rows | `--lowercase --dedup` | 666,313,875 bytes ≈ 666 MB | 12,671,936 | 4,281,184 |
| Full UMLS 2020AA, case-preserving | ≈ 1.97 GB, 15,479,756 rows | `--dedup` | 681,039,196 bytes ≈ 681 MB | 13,080,061 | 4,281,184 |

- **Level-0 subset:** used in the [original EMNLP 2026 Findings paper](https://aclanthology.org/2026.findings-emnlp.1109.pdf). The updated paper still uses it for the reranker ablations on EMEA and Patent.
- **Full release, lowercased:** used for the main results of the [updated paper](https://arxiv.org/abs/2605.27380). Several baseline numbers in our main table are taken from Con2GEN (Zhu et al., EMNLP 2023), whose reported UMLS 2020AA knowledge base has 12,671,936 names, exactly the size of this version.
- **Full release, case-preserving:** results are in Appendix F.2 of the [updated paper](https://arxiv.org/abs/2605.27380).

## UMLS-Wikidata
Download **[UMLS-Wikidata](https://zenodo.org/records/11003203)** and save it to `data/umls_wikidata`. We use this knowledge base to evaluate WikiMed-DE under the UMLS-Wikidata setting (`DE-wiki`).

### Convert UMLS-Wikidata to XL-BEL Knowledge Base Format
- Input: `umls_wikidata.jsonl`
- Output: a plain-text file with one record per line, `CUI||name` (e.g. `C0000392||beta-alanine`)

```bash
python code/process_kbs/umls_wikidata_to_xl_bel_format.py \
    --kb_path /path/to/umls_wikidata/umls_wikidata.jsonl \
    --output_path /path/to/save/the/converted/kb \
    --lowercase \
    --dedup
```
