# NFL Quarterback Rating System

A composite rating tool that scrapes QB stats from Pro Football Reference and ranks quarterbacks on a 0-100 scale with tier classifications.

## How It Works

The system scrapes seasonal passing stats and computes a weighted composite score using 8 key metrics:

| Stat | Weight | Why It Matters |
|------|--------|----------------|
| Y/A (Yards/Attempt) | 18% | Best single measure of passing efficiency |
| TD% | 15% | Scoring efficiency per attempt |
| INT% | 15% | Turnover avoidance (lower is better) |
| ANY/A (Adj Net Yds/Att) | 15% | Accounts for sacks, TDs, and INTs together |
| Cmp% | 12% | Passing accuracy |
| Win% | 10% | Winning as a starter |
| Sk% (Sack Rate) | 8% | Pocket awareness (lower is better) |
| Y/G (Yards/Game) | 7% | Volume production per game |

Stats are min-max normalized across all qualifying QBs, then combined into a weighted score scaled to 0-100.

### Tier Classification

| Score | Tier |
|-------|------|
| 80+ | Elite |
| 65-79 | Great |
| 45-64 | Average |
| 30-44 | Below Average |
| 0-29 | Poor |

## Usage

### CLI
```bash
python qb_rating.py
```
Enter the season year, minimum pass attempts, and how many QBs to display.

### Notebook
Open `../notebooks/qb_rating_analysis.ipynb` for interactive visualizations including bar charts, radar charts, and scatter plots.

## Data Source

Primary: [nflverse](https://github.com/nflverse/nflverse-data) open-source NFL data (weekly player stats aggregated to season totals).
Fallback: [Pro Football Reference](https://www.pro-football-reference.com) HTML scraping.

Data is cached locally after the first download to avoid repeated network requests.

## Requirements

- Python 3.10+
- pandas, numpy, matplotlib, seaborn
- requests, lxml, beautifulsoup4
