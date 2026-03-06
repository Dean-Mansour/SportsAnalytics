# Dean Mansour
# NFL Quarterback Rating System

"""
CLI tool that scrapes QB stats from Pro Football Reference,
computes a composite rating, and displays ranked results with tier labels.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from scraper import fetch_passing_stats, filter_qualified_qbs
from rating_engine import compute_ratings


def print_rankings(df, year, top_n=None):
    """Print a formatted ranking table."""
    title = f"{year} QB Rankings"
    if top_n:
        title += f" (Top {top_n})"

    print(f"\n--- {title} ---")
    print(f"{'Rank':<6}{'Player':<24}{'Team':<6}{'Score':<8}{'Tier'}")
    print(f"{'----':<6}{'--------------------':<24}{'----':<6}{'-----':<8}{'---------------'}")

    for i, row in df.iterrows():
        rank = i + 1
        print(f"{rank:<6}{row['Player']:<24}{row['Tm']:<6}{row['Composite_Score']:<8}{row['Tier']}")


def print_tier_summary(df):
    """Print how many QBs fall into each tier."""
    tier_order = ["Elite", "Great", "Average", "Below Average", "Poor"]

    print("\n--- Tier Distribution ---")
    for tier in tier_order:
        count = len(df[df["Tier"] == tier])
        if count > 0:
            print(f"{tier + ':':<18}{count} QBs")


def print_top_stats(df):
    """Print the top QB in key stat categories."""
    print("\n--- Category Leaders ---")

    categories = [
        ("Cmp%", "Completion %", True),
        ("Y/A", "Yards/Attempt", True),
        ("TD%", "TD %", True),
        ("Int%", "INT % (lowest)", False),
        ("ANY/A", "Adj Net Yds/Att", True),
        ("Y/G", "Yards/Game", True),
    ]

    for col, label, ascending in categories:
        if col in df.columns:
            if ascending:
                best = df.loc[df[col].idxmax()]
            else:
                best = df.loc[df[col].idxmin()]
            print(f"{label + ':':<22}{best['Player']:<20}({best[col]})")


def main():
    """Main CLI entry point."""
    print("=" * 60)
    print("  NFL Quarterback Rating System")
    print("=" * 60)

    # --- User Inputs ---
    year_input = input("\nWhich NFL season year? (e.g. 2024): ").strip()
    year = int(year_input)

    min_input = input("Minimum pass attempts (default 200): ").strip()
    min_attempts = int(min_input) if min_input else 200

    top_input = input("Show top N QBs? (default: all): ").strip()
    top_n = int(top_input) if top_input else None

    print(f"\nFetching {year} passing stats...")

    # --- Scrape + Clean ---
    df = fetch_passing_stats(year)
    df = filter_qualified_qbs(df, min_attempts=min_attempts)

    if df.empty:
        print("No qualifying QBs found. Try lowering the minimum attempts.")
        return

    print(f"Found {len(df)} qualifying QBs (>= {min_attempts} attempts)")

    # --- Compute Ratings ---
    rated_df = compute_ratings(df)

    display_df = rated_df.head(top_n) if top_n else rated_df

    # --- Display Results ---
    print_rankings(display_df, year, top_n)
    print_tier_summary(rated_df)
    print_top_stats(rated_df)

    print("\n" + "=" * 60)
    print("  Rating uses: Y/A, TD%, INT%, ANY/A, Cmp%, Win%, Sk%, Y/G")
    print("  Weighted composite score normalized across all qualifiers")
    print("=" * 60)


if __name__ == "__main__":
    main()
