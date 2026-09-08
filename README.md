# BioELX

## Overview
BioELX is a two-stage framework for context-aware cross-lingual biomedical entity linking, consisting of a retriever for cross-lingual candidate retrieval and a reranker for context-aware entity disambiguation, without requiring task-specific BEL supervision.

![BioELX pipeline: a retriever fetches top-k cross-lingual candidates from the KB, then a reranker scores each candidate against the mention in its context.](misc/pipeline.png)

Stage 1 retrieves top-k candidate entities for a mention across languages; stage 2
extends the mention with its context (`<tgt>...</tgt>`) and reranks those candidates.

---
This repository includes code for data processing, retriever training and inference, and reranker inference.
## Citing
If you use BioELX in your work, please cite the following paper:
```bash
@article{DBLP:journals/corr/abs-2605-27380,
  author       = {Yi Wang and
                  Corina Dima and
                  Liangyu Zhong and
                  Steffen Staab},
  title        = {{BioELX: Context-Aware Cross-lingual Biomedical Entity Linking without Task-Specific Supervision}},
  journal      = {EMNLP 2026 Findings},
  volume       = {abs/2605.27380},
  year         = {2026},
  url          = {https://doi.org/10.48550/arXiv.2605.27380},
  doi          = {10.48550/ARXIV.2605.27380},
  eprinttype   = {arXiv},
  eprint       = {2605.27380},
  timestamp    = {Mon, 15 Jun 2026 06:25:34 +0200},
  biburl       = {https://dblp.org/rec/journals/corr/abs-2605-27380.bib},
  bibsource    = {dblp computer science bibliography, https://dblp.org}
}
```

## Huggingface Resources
Model:
> **[`bioelx-nlp/bioelx_retriever`](https://huggingface.co/bioelx-nlp/bioelx_retriever)**

Dataset:
> **[`bioelx-nlp/bioelx_wikidata_pairs`](https://huggingface.co/datasets/bioelx-nlp/bioelx_wikidata_pairs)**

## Setting up
Python 3.12

Create virtual environment:
```bash
python3.12 -m venv .bioelx
source .bioelx/bin/activate
```

Install the required dependencies with:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Datasets and results default to `data/` and `output/` inside the repository (see
[constants.py](code/common/constants.py)). If they live elsewhere -- on a scratch
filesystem, for instance -- point these environment variables at them instead:

```bash
export BIOELX_DATA_DIR=/path/to/data
export BIOELX_OUTPUT_DIR=/path/to/output
```

## Evaluation Datasets
- XL-BEL: **[sapbert repository](https://github.com/cambridgeltl/sapbert/tree/main/evaluation/xl_bel)**, XL-BEL dataset is in `sapbert/tree/main/evaluation/`
- EMEA and Patent: **[Mantra GSC](https://github.com/mi-erasmusmc/Mantra-Gold-Standard-Corpus)**
    - *Note*: There are two version of Mantra dataset, we use the original version published on 2015 in our implementation, which is more difficult than the other version.
    - We use `Mantra-GSC-XML.zip` in our implementation
    - Store it to `data/mantra`
- WikiMed-DE: **[WikiMed-DE on Zenodo](https://zenodo.org/records/8188966)**
    - details of this dataset please check this **[repository](https://github.com/AI4MedCode/wikimed-de)**
    - Store it to `data/wikimed_de`
- MedMentions: **[MedMentions repository](https://github.com/chanzuckerberg/MedMentions)**, we use st21pv version in our implementation 

## Preprocessing datasets
All three annotated corpora are converted by a single script, selected with `--dataset`.

- Input:
    - `mantra/Mantra-GSC-XML.zip`
    - `medmentions/corpus_pubtator.txt` (the st21pv corpus, decompressed) together with the
      three pmid split lists `medmentions/corpus_pubtator_pmids_trng.txt`,
      `medmentions/corpus_pubtator_pmids_dev.txt`, `medmentions/corpus_pubtator_pmids_test.txt`
    - `wikimed_de/test_data_bel.json`

- Output:
    - `.txt` files in XL-BEL format, for example `C0018544||halogène||Procédé de préparation...`,
      where the mention occurrence in the context is wrapped in `<tgt>...</tgt>`
    - saved to `data/mantra/processed/<bucket>/<lang>.txt` (buckets: `EMEA`, `Medline`, `Patent`),
      `data/medmentions/processed/{train,dev,test}.txt` (split by the pmid lists) and
      `data/wikimed_de/processed/test.txt`

- run

With no other arguments, inputs are read from `DATA_DIR/<dataset>` (see
[constants.py](code/common/constants.py)) and outputs are written to
`<input dir>/processed`. Both can be overridden, and `--splits` restricts which
subsets are written:

```bash
python code/preprocessing/to_xl_bel_format.py \
    --dataset mantra \
    --data_path /path/to/data/mantra \       
    --output_path /path/to/save/the/converted/data \
    --splits EMEA Patent                       # default: all buckets

python code/preprocessing/to_xl_bel_format.py --dataset medmentions 
python code/preprocessing/to_xl_bel_format.py --dataset wikimed-de --splits test
```

## Training Dataset

- Followin the instruction in [Wikidata README](wikidata/README.md) to obtain the training data `training_file_wikidata2025_uncased_no_dup_pairwise_pair_th.txt`

## Knowledge Bases

follow the instructions in [process_kbs](process_kbs/README.md)

## Train Retriever
> Only needed if you want to retrain. To just run the pipeline, use our released checkpoint — see [Run Retrieval](#run-retrieval).
- download the **[sapbert repository](https://github.com/cambridgeltl/sapbert/)**
- Follow the instruction of sapbert repository and replace the sapbert training data to ours

## Run Retrieval
**No training required** — our trained retriever is released on the Hugging Face Hub:

> **[`bioelx-nlp/bioelx_retriever`](https://huggingface.co/bioelx-nlp/bioelx_retriever)**

Pass the model id directly to `--sapbert_model`; the weights are downloaded and cached
automatically by `transformers` on first use. A local path to your own checkpoint
(e.g. from [Train Retriever](#train-retriever)) works exactly the same way.

- Inputs:
    - the dataset you want to evaluate. The data should be in XL-BEL format. For example,
    ```txt
    C2295058||Lackschildläusen||Die Laccainsäuren ...
    C0009968||Garkupfer||Saigerhütten  gewannen   <tgt>Garkupfer</tgt>  und  Silber ...
    ```
    - The corresponding knowledge base for the dataset, for example UMLS 2020AA for EMEA dataset.
- Outputs:
    - a txt file containing the mention, its context and the top-k possible candidates.
    - for example:
```txt
[
  {
    "mention": "Lackschildläusen",
    "context_left": "Die Laccainsäuren sind ...",
        "context_right": "  gewonnen wird.",
    "label": [
      "C2295058"
    ],
    "candidate_cuis": [
      "C1002908",
      "C1002908",
      "C1002908",
      ...
      ],
    "candidate_labels": [
      "Laccaria",
      "Laccaria",
      "Laccarias",
      ...
      ],
    "scores": [
      0.802098274230957,
      0.802098274230957,
      0.7999044060707092,
      ...
       ]
  },
  ...
]
```
- Run the following command line:

```bash
python code/sapbert_cl_ctx.py\
  --sapbert_model "bioelx-nlp/bioelx_retriever" \
  --kb_path "the_path_of_the_knowledge_base" \
  --mention_path "the_path_of_the_dataset_to_be_retrieved" \
  --output_path "the_path_you_want_to_store_the_retrieval_result" \
  --top_k 256 \ 
  --context \
  --cache_dir 
```

- `--sapbert_model`: `bioelx-nlp/bioelx_retriever` (our released checkpoint) or a local path to your own
- `--top_k`: integer, how many top-k candidates to keep for each mention
- `--context`: include the mention context in the retrieval query
- `--cache_dir`: where the knowledge base entity embeddings are cached, so they are not recomputed on the next 

## Run Reranking
- Inputs:
  - the retrieved candidates, which is obtained after running retrieval
- Outputs:
  - the reranked results 

```bash
python /code/qwen_inference.py \
  --output_path "the_path_you_want_to_store_the_rerank_result" \
  --data_path "the_path_you_store_the_retrieval_result" \
  --model_size 8B \
  --top_k 16 \
  --cuda cuda:0
```

## Evaluation
See [evaluation example](./code/evaluation/eval_example.ipynb)
