"""评测指标计算 — 分类、检索、NER、文本重叠等。"""

from __future__ import annotations

import math
import re
from typing import Sequence


def accuracy(correct: int, total: int) -> float:
    return correct / total if total else 0.0


def precision_recall_f1(
    tp: int,
    fp: int,
    fn: int,
) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def macro_f1(per_class_f1: list[float]) -> float:
    return sum(per_class_f1) / len(per_class_f1) if per_class_f1 else 0.0


def set_f1(expected: set[str], predicted: set[str]) -> float:
    if not expected and not predicted:
        return 1.0
    tp = len(expected & predicted)
    _, _, f1 = precision_recall_f1(tp, len(predicted - expected), len(expected - predicted))
    return f1


def entity_f1(expected: dict[str, str], predicted: dict[str, str]) -> float:
    if not expected and not predicted:
        return 1.0
    tp = sum(1 for k, v in expected.items() if predicted.get(k, "").upper() == v.upper())
    fp = len(predicted) - tp
    fn = len(expected) - tp
    _, _, f1 = precision_recall_f1(tp, fp, fn)
    return f1


def recall_at_k(ranked_ids: Sequence[str], gold_id: str, k: int) -> float:
    top = ranked_ids[:k]
    return 1.0 if gold_id in top else 0.0


def mrr_at_k(ranked_ids: Sequence[str], gold_id: str, k: int) -> float:
    for i, doc_id in enumerate(ranked_ids[:k]):
        if doc_id == gold_id:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(relevances: Sequence[float], k: int) -> float:
    """relevances: 按检索排序位置的相关性分数 (0/1 或 graded)。"""
    rels = list(relevances[:k])
    if not rels:
        return 0.0

    def dcg(scores: Sequence[float]) -> float:
        return sum(s / math.log2(i + 2) for i, s in enumerate(scores))

    ideal = sorted(relevances, reverse=True)[:k]
    idcg = dcg(ideal)
    return dcg(rels) / idcg if idcg else 0.0


def keyword_coverage(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


def token_overlap_f1(reference: str, hypothesis: str) -> float:
    """基于词袋的简单语义重叠 F1（无 embedding 时的 faithfulness 代理指标）。"""
    ref_tokens = set(_tokenize(reference))
    hyp_tokens = set(_tokenize(hypothesis))
    if not ref_tokens and not hyp_tokens:
        return 1.0
    tp = len(ref_tokens & hyp_tokens)
    _, _, f1 = precision_recall_f1(tp, len(hyp_tokens - ref_tokens), len(ref_tokens - hyp_tokens))
    return f1


def contains_all_fields(text: str, fields: list[str]) -> bool:
    return all(f in text for f in fields)


def calibration_ece(confidences: list[float], correct_flags: list[bool], n_bins: int = 10) -> float:
    """Expected Calibration Error — 置信度与真实准确率的偏差。"""
    if not confidences:
        return 0.0
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for conf, ok in zip(confidences, correct_flags, strict=False):
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, ok))

    ece = 0.0
    total = len(confidences)
    for bucket in bins:
        if not bucket:
            continue
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        avg_acc = sum(1 for _, ok in bucket if ok) / len(bucket)
        ece += (len(bucket) / total) * abs(avg_conf - avg_acc)
    return ece


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
