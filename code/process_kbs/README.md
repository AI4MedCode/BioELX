# Knowledge Bases
## UMLS-399931
This knowledge base can be downloaded along with XL-BEL and is used to evaluate XL-BEL. This knowledge base is ready to use. We do not need to do any modification on it.

## UMLS
1. Visit **[the UMLS Knowledge Sources](https://www.nlm.nih.gov/research/umls/licensedcontent/umlsknowledgesources.html)** to download UMLS Metathesauruus Full Subset
2. For history versions of UMLS, go **[the UMLS history archive](https://www.nlm.nih.gov/research/umls/licensedcontent/umlsarchives04.html)**

We use two versions of UMLS in our implementation:
- UMLS 2020AA, to be comparable with other papers, we use this version of UMLS to evaluate EMEA and Patent
- UMLS 2017AA, to be comparable with other papers, we use this version of UMLS to evaluate MedMentions

### Convert UMLS to XL-BEL Knowledge Base Format

Reads a UMLS `MRCONSO.RRF` file, extracts each `(CUI, name)` pair, and writes one alias per line in the xl-bel format `CUI||name`.

- Inputs:
    - `MRCONSO.RRF` 
- Outputs:
    - A plain-text file, one record per line, `CUI||name` (e.g. `C0000392||beta-alanine`).
- Example commands:

```bash
python code/process_kbs/umls_to_xl_bel_format.py \
    --kb_path  /path/to/umls/MRCONSO.RRF \
    --output_path /path/to/save/the/converted/kb \
    --lowercase \ # lowercase the text
    --dedup # remove duplicated rows
```

## UMLS-Wikidata
Download **[UMLS-Wikidata](https://zenodo.org/records/11003203)** and save it to `data/umls_wikidata`, we use this knowledge base to evaluate WikiMed-DE.

### Convert UMLS-Wikidata to XL-BEL Knowledge Base Format
- Inputs:
    - `umls_wikidata.jsonl` 
- Outputs:
    - A plain-text file, one record per line, `CUI||name` (e.g. `C0000392||beta-alanine`).
- Example commands:

```bash
python code/process_kbs/umls_wikidata_to_xl_bel_format.py \
    --kb_path  /path/to/umls_wikidata/umls_wikidata.jsonl \
    --output_path /path/to/save/the/converted/kb \
    --lowercase \ # lowercase the text
    --dedup # remove duplicated rows
```


