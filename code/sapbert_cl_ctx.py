import os
import json
import numpy as np
import torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModel
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from common.params import BioELXParser
from common.utils import save_torch, load_torch, save_json, load_json, ensure_parent_dir

def load_kb(kb_path):
    kb_cuis = []
    kb_names = []
    with open(kb_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("||")
            if len(parts) < 2:
                continue
            cui = parts[0].strip()
            name = parts[1].strip()
            if not cui or not name:
                continue
            kb_cuis.append(cui)
            kb_names.append(name)
    return kb_cuis, kb_names


def load_mentions(mention_path, context=False):
    def split_ctx(ctx_text: str, mention_text: str):
        if not ctx_text:
            return "", ""
     
        if "<tgt>" in ctx_text and "</tgt>" in ctx_text:
            try:
                left, rest = ctx_text.split("<tgt>", 1)
                _inside, right = rest.split("</tgt>", 1)
                return left, right
            except Exception:
                pass
 
        idx = ctx_text.find(mention_text)
        if idx != -1:
            return ctx_text[:idx], ctx_text[idx + len(mention_text):]
        return "", ""

    mentions = []
    with open(mention_path, "r", encoding="utf-8") as f:
        for line_id, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            parts = line.split("||")
            if len(parts) < 2:
                continue

            cui_part = parts[0].strip()
            label_cuis = [c.strip() for c in cui_part.split("|") if c.strip()]

            mention_text = parts[1].strip()

            ctx_text = ""
            ctx_left, ctx_right = "", ""

            if context:
                ctx_text = "||".join(parts[2:]).strip() if len(parts) > 2 else ""
                ctx_left, ctx_right = split_ctx(ctx_text, mention_text)
                # Keep context for storage, but only encode the mention itself for ranking
                query_text = mention_text
            else:
                query_text = mention_text

            mentions.append({
                "mention": mention_text,
                "label": label_cuis,
                "raw_line": line,
                "line_id": line_id,
                "query_text": query_text,
                "context": ctx_text,
                "context_left": ctx_left,
                "context_right": ctx_right,
            })
    return mentions


@torch.no_grad()
def encode_texts(texts, model, tokenizer, device, batch_size=128, max_length=25):
    all_embs = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Encoding"):
        batch_texts = texts[i:i + batch_size]
        toks = tokenizer(
            batch_texts,
            padding="max_length",
            max_length=max_length,
            truncation=True,
            return_tensors="pt",
        )
        toks = {k: v.to(device) for k, v in toks.items()}
        outputs = model(**toks)
        cls_rep = outputs.last_hidden_state[:, 0, :]
        all_embs.append(cls_rep.detach().cpu().numpy())
    return np.concatenate(all_embs, axis=0)


def l2_normalize(x: torch.Tensor, dim=1, eps=1e-12):
    return x / (x.norm(p=2, dim=dim, keepdim=True).clamp_min(eps))


@torch.no_grad()
def retrieve_topk(mention_embs, kb_embs, kb_cuis, kb_names, top_k=64):
    results = []
    for i in tqdm(range(mention_embs.size(0)), desc="Retrieving"):
        q = mention_embs[i:i + 1]
        sims = torch.mm(q, kb_embs.t()).squeeze(0)
        topk_vals, topk_idxs = torch.topk(sims, k=min(top_k, sims.size(0)))

        idxs = topk_idxs.tolist()
        results.append({
            "candidate_cuis": [kb_cuis[j] for j in idxs],
            "candidate_labels": [kb_names[j] for j in idxs],
            "scores": topk_vals.detach().cpu().tolist(),
            "candidate_indices": idxs,
        })
    return results


def main(params):
    device = params.get("device", None)
    if device is None or device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model_name = params["sapbert_model"]
    kb_path = params["kb_path"]
    mention_path = params["mention_path"]
    output_json = params["output_path"]

    batch_size = int(params["batch_size"])
    max_length = int(params["max_length"])
    top_k = int(params["top_k"])
    use_context = bool(params["context"])
    force_reencode = bool(params["force_reencode"])

    cache_dir = params.get("cache_dir", None)
    if cache_dir is None:
        cache_dir = str(Path(output_json).parent)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    kb_emb_path = params.get("kb_emb_path") or os.path.join(cache_dir, "kb_embs.pt")
    kb_meta_path = params.get("kb_meta_path") or os.path.join(cache_dir, "kb_meta.json")
    ensure_parent_dir(output_json)

    print(f"[config] device={device}")
    print(f"[config] model={model_name}")
    print(f"[config] kb_path={kb_path}")
    print(f"[config] mention_path={mention_path}")
    print(f"[config] output={output_json}")
    print(f"[config] cache_dir={cache_dir}")
    print(f"[config] top_k={top_k}, batch_size={batch_size}, max_length={max_length}, context={use_context}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    mention_model = AutoModel.from_pretrained(model_name).to(device).eval()
    kb_model = AutoModel.from_pretrained(model_name).to(device).eval()

    kb_cuis, kb_names = load_kb(kb_path)
    print(f"[KB] entries={len(kb_cuis)}")

    if (not force_reencode) and os.path.exists(kb_emb_path) and os.path.exists(kb_meta_path):
        kb_embs = load_torch(kb_emb_path, device)
        kb_meta = load_json(kb_meta_path)
        kb_cuis = kb_meta["cuis"]
        kb_names = kb_meta["names"]
        print(f"[KB] loaded cached embeddings: {kb_embs.shape}")
    else:
        print("[KB] encoding...")
        kb_embs_np = encode_texts(kb_names, kb_model, tokenizer, device, batch_size=batch_size, max_length=max_length)
        kb_embs = torch.tensor(kb_embs_np, dtype=torch.float32, device='cpu')
        
        print("[KB] normalizing embeddings in batches...")
        batch_size_norm = 50000
        normalized_batches = []
        for i in range(0, len(kb_embs), batch_size_norm):
            batch = kb_embs[i:i+batch_size_norm].to(device)
            normalized_batch = l2_normalize(batch, dim=1).cpu()
            normalized_batches.append(normalized_batch)
            torch.cuda.empty_cache()
        kb_embs = torch.cat(normalized_batches, dim=0).to(device)
        
        save_torch(kb_emb_path, kb_embs)
        save_json(kb_meta_path, {"cuis": kb_cuis, "names": kb_names})
        print(f"[KB] encoded embeddings: {kb_embs.shape}")

    mentions = load_mentions(mention_path, context=use_context)
    query_texts = [m["query_text"] for m in mentions]
    print(f"[Mention] count={len(query_texts)}")

    print("[Mention] encoding...")
    mention_embs_np = encode_texts(query_texts, mention_model, tokenizer, device, batch_size=batch_size, max_length=max_length)
    mention_embs = torch.tensor(mention_embs_np, dtype=torch.float32, device=device)
    mention_embs = l2_normalize(mention_embs, dim=1)
    print(f"[Mention] encoded embeddings: {mention_embs.shape}")

    retrieved = retrieve_topk(mention_embs, kb_embs, kb_cuis, kb_names, top_k=top_k)

    final_results = []
    for m, r in zip(mentions, retrieved):
        final_results.append({
            "mention": m["mention"],
            "label": m["label"],
            "context_left": m.get("context_left", ""),
            "context_right": m.get("context_right", ""),
            "candidate_cuis": r["candidate_cuis"],
            "candidate_labels": r["candidate_labels"],
            "scores": r["scores"],
            "candidate_indices": r["candidate_indices"],
        })

    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)

    print("[done] saved:", output_json)


if __name__ == "__main__":
    parser = BioELXParser(add_model_args=True)

    args = parser.parse_args()
    main(vars(args))
