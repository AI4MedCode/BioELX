import os
import sys
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
sys.path.append(str(Path(__file__).resolve().parent.parent))
from common import utils
from common.params import BioELXParser


def keep_top_k_simple(items: List[Dict[str, Any]], k: int = 32) -> List[Dict[str, Any]]:
    out = []
    for x in items:
        cands = x.get("candidate_cuis", [])
        descs = x.get("candidate_labels", [])
        y = dict(x)
        y["candidate_cuis"] = cands[:k]
        y["candidate_labels"] = descs[:k]
        out.append(y)
    return out


class QwenReranker:
    def __init__(self, params: Dict[str, Any]):
        self.model_id = f"Qwen/Qwen3-Reranker-{params['model_size']}"
        self.device = torch.device(params["cuda"] if torch.cuda.is_available() else "cpu")
        self.lora_path = params.get("lora_path", None)
        self.lora = params.get("lora", False)
        self.qwen_max_length = int(params["qwen_max_length"])
        self.only_mention = bool(params["only_mention"])
        self.short_context = bool(params["short_context"])

        self.score_batch_size = int(params.get("score_batch_size", 16))
        self.print_input_shapes = bool(params.get("print_input_shapes", False))

        self.dtype = torch.float16
        if self.device.type == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.benchmark = True

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, padding_side="left", use_fast=False)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        if self.lora:
            self.base_model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                torch_dtype=self.dtype,
                attn_implementation="flash_attention_2",
            ).to(self.device).eval()

            self.model = PeftModel.from_pretrained(self.base_model, self.lora_path, torch_dtype=self.dtype).to(self.device).eval()
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=self.dtype,
            attn_implementation="flash_attention_2",
        ).to(self.device).eval()

        self.token_false_id = self.tokenizer.convert_tokens_to_ids("no")
        self.token_true_id = self.tokenizer.convert_tokens_to_ids("yes")

        self.prefix = (
            "<|im_start|>system\n"
            "You are a multilingual biomedical entity linking reranker. "
            "Judge whether the Document meets the requirements based on the Query and the Instruct provided. "
            "Note that the answer can only be \"yes\" or \"no\"."
            "<|im_end|>\n"
            "<|im_start|>user\n"
        )

        self.suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

        self.prefix_tokens = self.tokenizer.encode(self.prefix, add_special_tokens=False)
        self.suffix_tokens = self.tokenizer.encode(self.suffix, add_special_tokens=False)

    def format_instruction(self, query: str, doc: str) -> str:
        if self.only_mention:
            instruction = (
                "Given a query that is ONLY a single biomedical mention (no extra context), "
                "match it to the best fitting English canonical entity name."
            )
        else:
            instruction = (
            "Given a Query (in any language) containing a target mention marked by <tgt>...</tgt> "
            "and its local context (nearby words/sentences), and a Document containing a candidate entity name in any language, "
            "decide whether the candidate is the correct link for the mention in context.")

        return (
            f"<Instruct>: {instruction}\n"
            f"<Query>: {query}\n"
            f"<Document>: {doc}"
        )

    def process_inputs(self, pairs: List[str]) -> Dict[str, torch.Tensor]:
        max_text_len = self.qwen_max_length - len(self.prefix_tokens) - len(self.suffix_tokens)

        inputs = self.tokenizer(
            pairs,
            padding=False,
            truncation="longest_first",
            return_attention_mask=True,   
            max_length=max_text_len,
        )

        for i in range(len(inputs["input_ids"])):
            ids = inputs["input_ids"][i]
            mask = inputs["attention_mask"][i]
            inputs["input_ids"][i] = self.prefix_tokens + ids + self.suffix_tokens
            inputs["attention_mask"][i] = [1] * len(self.prefix_tokens) + mask + [1] * len(self.suffix_tokens)

        inputs = self.tokenizer.pad(
            inputs,
            padding=True,
            return_tensors="pt",
            max_length=self.qwen_max_length,
        )

        return {k: v.to(self.device) for k, v in inputs.items()}

    @torch.inference_mode()
    def compute_logits(self, inputs: Dict[str, torch.Tensor]) -> List[float]:
        try:
            out = self.model(**inputs, use_cache=False, logits_to_keep=1)
        except TypeError:
            out = self.model(**inputs, use_cache=False)

        last_logits = out.logits[:, -1, :]

        true_vector = last_logits[:, self.token_true_id]
        false_vector = last_logits[:, self.token_false_id]

        yn = torch.stack([false_vector, true_vector], dim=1)  
        yn = torch.nn.functional.log_softmax(yn, dim=1)
        scores = yn[:, 1].exp().detach().cpu().tolist()
        return scores

    @torch.inference_mode()
    def rerank_item(self, item: Dict[str, Any], top_k: int = None) -> List[Dict[str, Any]]:
        mention = str(item["mention"])
        if self.only_mention:
            text = mention
        elif self.short_context:
            text = item["context_left_1"] + " " + "*" + item["mention"] + "*" + " " + item["context_right_1"]
        else:
            text = item["context_left"] + " " + "<tgt>" + item["mention"] + "</tgt>" + " " + item["context_right"]
        cuis = [str(c) for c in item["candidate_cuis"]]
        descs = [d.replace("\n", " ").strip() for d in item["candidate_labels"]]

        queries = [text] * len(cuis)
        candidate_texts = descs
        pairs = [self.format_instruction(q, d) for q, d in zip(queries, candidate_texts)]
        scores: List[float] = []
        for s in range(0, len(pairs), self.score_batch_size):
            chunk_pairs = pairs[s:s + self.score_batch_size]
            inputs = self.process_inputs(chunk_pairs)
            if self.print_input_shapes:
                print("input_ids shape:", inputs["input_ids"].shape, inputs["input_ids"][0].shape)
            scores.extend(self.compute_logits(inputs))
            del inputs

        order = np.argsort(scores)[::-1]
        if top_k is not None:
            order = order[:top_k]

        out = []
        for r, idx in enumerate(order, start=1):
            out.append(
                {
                    "rank": r,
                    "score": float(scores[idx]),
                    "cui": cuis[idx],
                    "description": descs[idx],
                }
            )
        return out

    def rerank_items(self, items: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        outputs = []
        for it in tqdm(items):
            results = self.rerank_item(it, top_k=top_k)
            outputs.append(
                {
                    "mention": it.get("mention"),
                    "label_id": it.get("label"),
                    "results": results,
                }
            )
        return outputs


if __name__ == "__main__":
    parser = BioELXParser(add_model_args=True)
    parser.add_qwen_args()

    args = parser.parse_args()
    print(args)

    params = args.__dict__

    out_path = params["output_path"]
    os.makedirs(out_path, exist_ok=True)

    logger = utils.get_logger(out_path)
    logger.info(
        f"Reranking with Qwen3-Reranker-{params['model_size']}, top_k={params['top_k']}, only_mention={params['only_mention']}"
    )

    qwen_data_path = params["data_path"]
    data = utils.load_json(qwen_data_path)

    if params.get("debug", False):
        logger.info("Debug mode: only reranking 1 item from valid set")
        data = data[:1]
        out_file_name = f"reranked_{params['model_size']}_debug.json"
    elif params.get("only_mention", False):
        logger.info(f"Only mention mode: reranking all {len(data)} items from valid set")
        out_file_name = f"reranked_{params['model_size']}_{params['top_k']}_om_nst.json"
    else:
        logger.info(f"Full mode: reranking all {len(data)} items from valid set")
        out_file_name = f"reranked_{params['model_size']}_{params['top_k']}_ctx_nst.json"

    reranker = QwenReranker(params)
    valid_out = reranker.rerank_items(data, top_k=params["top_k"])

    save_path = os.path.join(out_path, out_file_name)
    print("saving to:", save_path)
    utils.save_json(save_path, valid_out)
