# Dean Mansour
# NFL Quarterback Rating System - Rating Engine

"""
Composite QB rating engine with weighted scoring and tier classification.
"""

import pandas as pd
import numpy as np

# Each entry: (column_name, weight, higher_is_better)
STAT_WEIGHTS = [
    ("Y/A",   0.18, True),
    ("TD%",   0.15, True),
    ("Int%",  0.15, False),
    ("ANY/A", 0.15, True),
    ("Cmp%",  0.12, True),
    ("Win%",  0.10, True),
    ("Sk%",   0.08, False),
    ("Y/G",   0.07, True),
]

TIER_THRESHOLDS = [
    (80, "Elite"),
    (65, "Great"),
    (45, "Average"),
    (30, "Below Average"),
    (0,  "Poor"),
]

TIER_COLORS = {
    "Elite":         "#1a9850",
    "Great":         "#91cf60",
    "Average":       "#fee08b",
    "Below Average": "#fc8d59",
    "Poor":          "#d73027",
}


def compute_ratings(df):
    """
    Compute the composite QB rating for each quarterback.

    Steps:
    1. Min-max normalize each stat across the QB population.
    2. Invert "lower is better" stats.
    3. Compute weighted sum.
    4. Scale to 0-100.
    5. Assign tier labels.
    6. Sort by score descending.

    Args:
        df: Cleaned, filtered DataFrame of qualifying QBs.

    Returns:
        DataFrame with 'Composite_Score', 'Tier', and '{stat}_norm' columns added.
    """
    rated = df.copy()

    # Determine which stats are available and have valid data
    active_weights = []
    for stat, weight, higher_is_better in STAT_WEIGHTS:
        if stat in rated.columns and rated[stat].notna().any():
            active_weights.append((stat, weight, higher_is_better))

    # Redistribute weights proportionally if some stats are missing
    total_weight = sum(w for _, w, _ in active_weights)
    scale_factor = 1.0 / total_weight if total_weight > 0 else 1.0

    weighted_sum = np.zeros(len(rated))

    for stat, weight, higher_is_better in active_weights:
        norm_col = f"{stat}_norm"
        rated[norm_col] = _normalize_stat(rated[stat], higher_is_better)
        adjusted_weight = weight * scale_factor
        weighted_sum += adjusted_weight * rated[norm_col].fillna(0)

    rated["Composite_Score"] = (weighted_sum * 100).round(1)
    rated["Tier"] = rated["Composite_Score"].apply(assign_tier)
    rated = rated.sort_values("Composite_Score", ascending=False).reset_index(drop=True)

    return rated


def _normalize_stat(series, higher_is_better):
    """
    Min-max normalize a stat column to [0, 1].

    For "lower is better" stats, the result is inverted so that
    the best value maps to 1 and the worst to 0.

    Args:
        series: Raw stat values.
        higher_is_better: If False, invert the normalization.

    Returns:
        Normalized Series.
    """
    min_val = series.min()
    max_val = series.max()

    if max_val == min_val:
        return pd.Series(0.5, index=series.index)

    normalized = (series - min_val) / (max_val - min_val)

    if not higher_is_better:
        normalized = 1 - normalized

    return normalized


def assign_tier(score):
    """
    Map a 0-100 composite score to a tier label.

    Args:
        score: Composite score from 0 to 100.

    Returns:
        Tier label string.
    """
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "Poor"


def get_tier_color(tier):
    """Return a hex color code for a tier (for visualizations)."""
    return TIER_COLORS.get(tier, "#999999")


if __name__ == "__main__":
    from scraper import fetch_passing_stats, filter_qualified_qbs

    df = fetch_passing_stats(2024)
    df = filter_qualified_qbs(df, min_attempts=200)
    rated = compute_ratings(df)
    print(rated[["Player", "Tm", "Composite_Score", "Tier"]].to_string(index=False))
