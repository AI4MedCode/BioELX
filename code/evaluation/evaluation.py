from typing import Iterable, Tuple, Dict, Any


class Stats:
    def __init__(self, top_k: int = 1000):
        self.cnt = 0
        self.hits = []
        self.top_k = top_k
        self.rank = [1, 4, 8, 16, 32, 64, 100, 128, 256, 512]
        self.LEN = len(self.rank)
        for _ in range(self.LEN):
            self.hits.append(0)

    def add(self, idx: int):
        self.cnt += 1
        if idx == -1:
            return
        for i in range(self.LEN):
            if idx < self.rank[i]:
                self.hits[i] += 1

    def extend(self, stats: "Stats"):
        self.cnt += stats.cnt
        for i in range(self.LEN):
            self.hits[i] += stats.hits[i]

    def output(self) -> str:
        output_json = "Total: %d examples." % self.cnt
        for i in range(self.LEN):
            if self.top_k < self.rank[i]:
                break
            output_json += " r@%d: %.4f" % (self.rank[i], self.hits[i] / float(self.cnt))
        return output_json


def eval_recall_sapbert(
    data: Iterable[Dict[str, Any]],
    ranks: Tuple[int, ...] = (1, 4, 8, 16, 32, 64),
    top_k: int = None,
    gold_key: str = "label",
    cand_list_key: str = "candidate_cuis",
):
    k_limit_default = max(ranks) if ranks else 1
    stats = Stats(top_k=top_k or k_limit_default)
    stats.rank = list(ranks)
    stats.LEN = len(stats.rank)
    stats.hits = [0] * stats.LEN

    for ex in data:
        gold = ex.get(gold_key)
        cands = ex.get(cand_list_key, []) or []

        if gold is None:
            gold_list = []
        elif isinstance(gold, (list, tuple, set)):
            gold_list = list(gold)
        else:
            gold_list = [gold]

        k_limit = top_k if top_k is not None else len(cands)
        if k_limit == 0 or not gold_list:
            stats.add(-1)
            continue

        pos = -1
        for g in gold_list:
            try:
                idx = cands.index(g)
                if pos == -1 or idx < pos:
                    pos = idx
            except ValueError:
                continue

        idx = pos if (pos != -1 and pos < k_limit) else -1
        stats.add(idx)

    recalls = {}
    if stats.cnt > 0:
        for i, k in enumerate(stats.rank):
            if stats.top_k < k:
                break
            recalls[k] = stats.hits[i] / float(stats.cnt)
    else:
        recalls = {k: 0.0 for k in ranks}

    return stats, recalls


def eval_recall_ranked(
    data: Iterable[Dict[str, Any]],
    ranks: Tuple[int, ...] = (1, 4, 8, 16, 32, 64),
    top_k: int = None,
    gold_key: str = "label_id",
    results_key: str = "results",
    cui_key: str = "cui",
    score_key: str = "score",
    score_tol: float = 0,
):
    k_limit_default = max(ranks) if ranks else 1
    stats = Stats(top_k=top_k or k_limit_default)
    stats.rank = list(ranks)
    stats.LEN = len(stats.rank)
    stats.hits = [0] * stats.LEN

    for ex in data:
        gold = ex.get(gold_key)
        results = ex.get(results_key, []) or []

        if gold is None:
            gold_set = set()
        elif isinstance(gold, (list, tuple, set)):
            gold_set = set(gold)
        else:
            gold_set = {gold}

        k_limit = top_k if top_k is not None else len(results)
        if k_limit == 0 or not gold_set:
            stats.add(-1)
            continue

        cleaned = []
        for r in results:
            cui = r.get(cui_key)
            sc = r.get(score_key)
            if cui is None or sc is None:
                continue
            cleaned.append((cui, float(sc)))
        if not cleaned:
            stats.add(-1)
            continue

        cleaned.sort(key=lambda x: x[1], reverse=True)

        max_score = cleaned[0][1]
        top1_set = {cui for cui, sc in cleaned if (max_score - sc) <= score_tol}

        if gold_set & top1_set:
            stats.add(0)
            continue

        truncated = cleaned[:k_limit]
        pos = -1
        for idx, (cui, _) in enumerate(truncated):
            if cui in gold_set:
                pos = idx
                break

        idx0 = pos if (pos != -1 and pos < k_limit) else -1
        stats.add(idx0)

    recalls = {}
    if stats.cnt > 0:
        for i, k in enumerate(stats.rank):
            if stats.top_k < k:
                break
            recalls[k] = stats.hits[i] / float(stats.cnt)
    else:
        recalls = {k: 0.0 for k in ranks}

    return stats, recalls


__all__ = ["Stats", "eval_recall_sapbert", "eval_recall_ranked"]
