# Dean Mansour
# NFL Quarterback Rating System - Web Scraper

"""
Fetches QB passing stats from nflverse (open-source NFL data) or Pro Football Reference.
Primary source: nflverse GitHub CSV files (reliable, open-source).
Fallback: Pro Football Reference HTML scraping (may be rate-limited).
"""

import requests
import pandas as pd
import os
import time

NFLVERSE_URL = "https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats_{year}.csv"
PFR_URL = "https://www.pro-football-reference.com/years/{year}/passing.htm"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def fetch_passing_stats(year, use_cache=True):
    """
    Fetch QB passing stats for a given season.

    Tries nflverse first (reliable open-source data), falls back to PFR scraping.

    Args:
        year: NFL season year (e.g. 2024).
        use_cache: If True, look for a cached CSV before downloading.

    Returns:
        Cleaned DataFrame with one row per qualifying QB.
    """
    cache_path = os.path.join(CACHE_DIR, f"qb_stats_{year}.csv")

    if use_cache and os.path.exists(cache_path):
        file_size = os.path.getsize(cache_path)
        if file_size > 0:
            return pd.read_csv(cache_path)

    # Try nflverse first (most reliable)
    try:
        df = _fetch_from_nflverse(year)
        print("  Data source: nflverse (open-source NFL data)")
    except Exception as e:
        print(f"  nflverse unavailable ({e}), trying Pro Football Reference...")
        try:
            html = _download_pfr_html(year)
            df = _parse_pfr_table(html)
            df = _clean_pfr_dataframe(df)
            print("  Data source: Pro Football Reference")
        except Exception as e2:
            raise RuntimeError(
                f"Could not fetch data from any source.\n"
                f"  nflverse error: {e}\n"
                f"  PFR error: {e2}\n"
                f"You can manually download stats and save to: {cache_path}"
            )

    os.makedirs(CACHE_DIR, exist_ok=True)
    df.to_csv(cache_path, index=False)

    return df


# ---------------------------------------------------------------------------
# nflverse data source (primary)
# ---------------------------------------------------------------------------

def _fetch_from_nflverse(year):
    """
    Download seasonal player stats from nflverse GitHub releases.
    Returns a cleaned DataFrame with aggregated QB passing stats.
    """
    url = NFLVERSE_URL.format(year=year)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    # Save temp file and read with pandas
    from io import StringIO
    df = pd.read_csv(StringIO(response.text), low_memory=False)

    # Filter to QB passing stats only
    df = df[df["position"] == "QB"].copy()

    # nflverse has weekly data - aggregate to season totals
    df = _aggregate_nflverse_season(df, year)

    return df


def _aggregate_nflverse_season(df, year):
    """
    Aggregate weekly nflverse stats into season totals per QB.
    Compute rate stats (Cmp%, TD%, INT%, Y/A, Y/G, etc.) from counting stats.
    """
    # Group by player and sum counting stats
    agg_cols = {
        "completions": "sum",
        "attempts": "sum",
        "passing_yards": "sum",
        "passing_tds": "sum",
        "interceptions": "sum",
        "sacks": "sum",
        "sack_yards": "sum",
        "passing_first_downs": "sum",
    }

    # Keep only columns that exist
    available_agg = {k: v for k, v in agg_cols.items() if k in df.columns}

    # Also grab the player's team (most recent) and games played
    grouped = df.groupby("player_display_name").agg(
        **{col: pd.NamedAgg(column=col, aggfunc=func)
           for col, func in available_agg.items()},
        G=pd.NamedAgg(column="week", aggfunc="count"),
        Tm=pd.NamedAgg(column="recent_team", aggfunc="last"),
    ).reset_index()

    # Rename to standard column names
    grouped = grouped.rename(columns={
        "player_display_name": "Player",
        "completions": "Cmp",
        "attempts": "Att",
        "passing_yards": "Yds",
        "passing_tds": "TD",
        "interceptions": "Int",
        "sacks": "Sk",
        "sack_yards": "Sk_Yds",
        "passing_first_downs": "1D",
    })

    # Compute rate stats
    grouped["Cmp%"] = (grouped["Cmp"] / grouped["Att"] * 100).round(1)
    grouped["TD%"] = (grouped["TD"] / grouped["Att"] * 100).round(1)
    grouped["Int%"] = (grouped["Int"] / grouped["Att"] * 100).round(1)
    grouped["Y/A"] = (grouped["Yds"] / grouped["Att"]).round(1)
    grouped["Y/G"] = (grouped["Yds"] / grouped["G"]).round(1)
    grouped["Y/C"] = (grouped["Yds"] / grouped["Cmp"]).round(1)

    # Sack rate: sacks / (attempts + sacks)
    total_dropbacks = grouped["Att"] + grouped["Sk"]
    grouped["Sk%"] = (grouped["Sk"] / total_dropbacks * 100).round(1)

    # Adjusted Net Yards per Attempt: (yards + 20*TD - 45*INT - sack_yards) / (attempts + sacks)
    grouped["ANY/A"] = (
        (grouped["Yds"] + 20 * grouped["TD"] - 45 * grouped["Int"] - grouped["Sk_Yds"])
        / total_dropbacks
    ).round(2)

    # NFL passer rating formula
    grouped["Rate"] = _compute_passer_rating(grouped)

    # Win% - nflverse doesn't have this directly, so we'll leave it as NaN
    # and the rating engine will handle missing values
    grouped["Win%"] = float("nan")

    # Try to compute wins from game results if available in the data
    # For now, Win% won't be used in the rating when sourced from nflverse

    return grouped


def _compute_passer_rating(df):
    """Compute NFL passer rating from counting stats."""
    a = ((df["Cmp"] / df["Att"]) - 0.3) * 5
    b = ((df["Yds"] / df["Att"]) - 3) * 0.25
    c = (df["TD"] / df["Att"]) * 20
    d = 2.375 - ((df["Int"] / df["Att"]) * 25)

    # Clamp each component to [0, 2.375]
    for comp in [a, b, c, d]:
        comp.clip(lower=0, upper=2.375, inplace=True)

    rating = ((a + b + c + d) / 6) * 100
    return rating.round(1)


# ---------------------------------------------------------------------------
# Pro Football Reference data source (fallback)
# ---------------------------------------------------------------------------

def _download_pfr_html(year):
    """Download raw HTML from PFR with rate limiting."""
    url = PFR_URL.format(year=year)

    time.sleep(3)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    return response.text


def _parse_pfr_table(html):
    """Parse the passing stats table from PFR HTML."""
    tables = pd.read_html(html, attrs={"id": "passing"})
    if not tables:
        raise ValueError("Could not find passing stats table on the page.")
    return tables[0]


def _clean_pfr_dataframe(df):
    """
    Clean the raw PFR DataFrame:
    - Flatten multi-level column headers
    - Remove repeated header rows
    - Strip * and + from player names
    - Handle multi-team players
    - Convert columns to numeric
    - Parse QBrec into Win%
    - Handle duplicate column names
    """
    # Flatten multi-level headers if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)

    # Handle duplicate 'Yds' columns (passing yards vs sack yards)
    cols = list(df.columns)
    yds_count = 0
    for i, col in enumerate(cols):
        if col == "Yds":
            yds_count += 1
            if yds_count == 2:
                cols[i] = "Sk_Yds"
    df.columns = cols

    # Remove repeated header rows (PFR inserts them every 30 rows)
    df = df[df["Rk"].astype(str) != "Rk"].copy()

    # Strip Pro Bowl (*) and All-Pro (+) markers from player names
    df["Player"] = df["Player"].str.replace(r"[*+]", "", regex=True).str.strip()

    # Handle multi-team players: keep total row (Tm contains 'TM'), drop per-team rows
    multi_team_players = df[df["Tm"].str.contains("TM", na=False)]["Player"].unique()
    rows_to_drop = []
    for player in multi_team_players:
        player_rows = df[df["Player"] == player]
        per_team_rows = player_rows[~player_rows["Tm"].str.contains("TM", na=False)]
        rows_to_drop.extend(per_team_rows.index.tolist())
    df = df.drop(rows_to_drop)

    # Define numeric columns to convert
    numeric_cols = [
        "Rk", "Age", "G", "GS", "Cmp", "Att", "Cmp%", "Yds", "TD", "TD%",
        "Int", "Int%", "1D", "Lng", "Y/A", "AY/A", "Y/C", "Y/G", "Rate",
        "Sk", "Sk_Yds", "Sk%", "NY/A", "ANY/A", "4QC", "GWD"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse QBrec (e.g. "11-6-0") into Wins, Losses, Ties, Win%
    if "QBrec" in df.columns:
        qbrec_split = df["QBrec"].str.split("-", expand=True)
        if qbrec_split.shape[1] >= 3:
            df["Wins"] = pd.to_numeric(qbrec_split[0], errors="coerce")
            df["Losses"] = pd.to_numeric(qbrec_split[1], errors="coerce")
            df["Ties"] = pd.to_numeric(qbrec_split[2], errors="coerce")
            total_games = df["Wins"] + df["Losses"] + df["Ties"]
            df["Win%"] = (df["Wins"] + 0.5 * df["Ties"]) / total_games
            df["Win%"] = df["Win%"].round(3)
        else:
            df["Win%"] = float("nan")
    else:
        df["Win%"] = float("nan")

    df = df.reset_index(drop=True)
    return df


def filter_qualified_qbs(df, min_attempts=200):
    """
    Filter to QBs with a minimum number of pass attempts.

    Args:
        df: Cleaned passing stats DataFrame.
        min_attempts: Minimum pass attempts to qualify.

    Returns:
        Filtered DataFrame.
    """
    return df[df["Att"] >= min_attempts].reset_index(drop=True)


if __name__ == "__main__":
    df = fetch_passing_stats(2024)
    df = filter_qualified_qbs(df, min_attempts=200)
    print(f"Found {len(df)} qualifying QBs")
    print(df[["Player", "Tm", "Att", "Cmp%", "Yds", "TD", "Int", "Y/A", "ANY/A"]].head(10).to_string())
