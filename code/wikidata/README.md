# Processing Wikidata aliases

## Obtaining wikidata aliases file
- Download `wikidatawiki-20251201-wb_items_per_site.sql.gz` from **[Wikidata dump 20251201](https://dumps.wikimedia.org/wikidatawiki/20251201/)**
- **Note**: We used the version 20251201 to for our implementation. Due to maintenance of wiki data, this link may become invalid. If it is invalid, please visit **[Wikidata dump](https://dumps.wikimedia.org/wikidatawiki/)** and select the version you want.
- store it under `BioELX/data/wikidata/raw`

## Obtain QID and CUI mapping
1. Run this query on [Wikidata Query Service](https://query.wikidata.org/)
```bash
SELECT ?cui ?qid WHERE {
  ?qid wdt:P2892 ?cui .
}
```
2. Download the result and rename it as ```qid_cui.csv```
3. Store qid_cui.csv in ```BioELX/data/wikidata/```
4. It returns 737,689 results (736,630 unique items). This number may change as Wikidata is continuously maintained and updated.

## Extracting wikidata items
- Inputs:
    - `wikidatawiki-20251201-wb_items_per_site.sql.gz`
    - `qid_cui.csv`
- Outputs:
    - `wb_items_per_site.csv`, triples in the term of `(QID, Language, Alias)`, for example, `(Q4763261,ar,أتلام وعائية)`
    - `wb_items_per_site_filtered.csv`, triples in the term of 4 tuples `(QID, Language, Alias, CUI)`, for example, `(Q4763261,ar,أتلام وعائية,C0002982)`
    - *Note*: Both files are stored under `BioELX/data/wikidata/processed`
- run 
```python
python code/wikidata/extract_items.py
```

Estimated running time: 802.51 seconds

## Generate data for training sapbert
- follow [sapbert repository](https://github.com/cambridgeltl/sapbert/) to run notebook [generate_pretraining_data_wikidata.ipynb](generate_pretraining_data_wikidata.ipynb)
- to filter the aliases in our evaluation benchmarks, you need to run `python code/preprocessing/to_xl_bel_format.py` first. Details see [Overall README](../../README.md).
- Output:
  - `training_file_wikidata2025_uncased_no_dup_pairwise_pair.txt`, `training_file_wikidata2025_uncased_no_dup_pairwise_pair_50.txt` training data
  - `debug_100.txt`
  - save to `data/sapbert/`