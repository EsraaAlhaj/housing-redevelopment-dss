"""Sensitivity analysis: how stable is the ranking when indicator weights vary?

Two local, non-AI techniques, both pure arithmetic on already-computed indicator
scores (no new "guessed" data is introduced):

1. One-at-a-time (OAT): vary a single indicator's weight by +/- delta, rescale the
   rest proportionally so weights still sum to 100, and track how far each
   project's rank moves.
2. Monte-Carlo weight perturbation: randomly jitter all weights within a band and
   repeat many trials, then report each project's rank range/std -> stability label.
"""
from __future__ import annotations

import random
import statistics
from typing import Optional

import pandas as pd

from src.core.scoring import composite_dataframe


def _rescale(weights: dict, changed_code: str, new_value: float) -> dict:
    others = {k: v for k, v in weights.items() if k != changed_code}
    others_sum = sum(others.values())
    remaining = max(0.0, 100.0 - new_value)
    if others_sum <= 0:
        return {**weights, changed_code: new_value}
    scaled = {k: (v / others_sum) * remaining for k, v in others.items()}
    scaled[changed_code] = new_value
    return scaled


def oat_sensitivity(projects: list, indicator_cfgs: list, study, base_weights: dict,
                     delta_pct: float = 10.0, steps: int = 2) -> pd.DataFrame:
    """For each indicator, perturb weight by -steps*delta..+steps*delta and record rank shifts."""
    records = []
    base_df = composite_dataframe(projects, indicator_cfgs, study, base_weights)
    base_rank = dict(zip(base_df["project_id"], base_df["rank"]))

    for code, w in base_weights.items():
        for mult in range(-steps, steps + 1):
            if mult == 0:
                continue
            new_w = max(0.0, min(100.0, w + mult * delta_pct))
            trial_weights = _rescale(base_weights, code, new_w)
            df = composite_dataframe(projects, indicator_cfgs, study, trial_weights)
            trial_rank = dict(zip(df["project_id"], df["rank"]))
            for pid, r in trial_rank.items():
                base_r = base_rank.get(pid)
                if base_r is None:
                    continue
                records.append({
                    "indicator": code,
                    "weight_delta": mult * delta_pct,
                    "project_id": pid,
                    "base_rank": base_r,
                    "trial_rank": r,
                    "rank_shift": r - base_r,
                })
    return pd.DataFrame(records)


def monte_carlo_stability(projects: list, indicator_cfgs: list, study, base_weights: dict,
                           trials: int = 60, jitter_pct: float = 15.0,
                           seed: Optional[int] = 42) -> pd.DataFrame:
    """Randomly jitter weights (renormalized to 100) across `trials` runs; summarize rank stability."""
    rng = random.Random(seed)
    base_df = composite_dataframe(projects, indicator_cfgs, study, base_weights)
    base_rank = dict(zip(base_df["project_id"], base_df["rank"]))
    name_by_id = dict(zip(base_df["project_id"], base_df["site_name"]))
    rank_history: dict[int, list[int]] = {pid: [] for pid in base_rank}

    codes = list(base_weights.keys())
    for _ in range(trials):
        jittered = {}
        for code in codes:
            w = base_weights[code]
            factor = 1 + rng.uniform(-jitter_pct, jitter_pct) / 100
            jittered[code] = max(0.0, w * factor)
        s = sum(jittered.values()) or 1.0
        jittered = {k: v / s * 100 for k, v in jittered.items()}
        df = composite_dataframe(projects, indicator_cfgs, study, jittered)
        for pid, r in zip(df["project_id"], df["rank"]):
            rank_history.setdefault(pid, []).append(r)

    rows = []
    for pid, ranks in rank_history.items():
        if not ranks:
            continue
        std = statistics.pstdev(ranks) if len(ranks) > 1 else 0.0
        rng_span = max(ranks) - min(ranks)
        if rng_span <= 1:
            label = "مستقر جدًا"
        elif rng_span <= 3:
            label = "مستقر"
        elif rng_span <= 6:
            label = "متوسط الحساسية"
        else:
            label = "شديد الحساسية"
        rows.append({
            "project_id": pid,
            "site_name": name_by_id.get(pid, ""),
            "base_rank": base_rank.get(pid),
            "rank_min": min(ranks),
            "rank_max": max(ranks),
            "rank_std": round(std, 2),
            "stability": label,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("base_rank").reset_index(drop=True)
    return out
