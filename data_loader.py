# use yahoo finance to load stock data for ticker listed in ticker.yaml
import yaml
import yfinance as yf
import pandas as pd
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TICKER_FILE = os.path.join(os.path.dirname(__file__), "ticker.yaml")


def load_tickers(path=TICKER_FILE):
    with open(path, "r") as f:
        return yaml.safe_load(f)["tickers"]


def download_data(tickers, start_date="2022-01-01", end_date="2025-01-01", batch_size=50):
    """Download historical daily data for a list of tickers from Yahoo Finance.

    Args:
        tickers: list of ticker symbols.
        start_date: start date string in "YYYY-MM-DD" format.
        end_date: end date string in "YYYY-MM-DD" format.
        batch_size: number of tickers to download per batch.

    Returns a dict of {ticker: DataFrame} with columns
    [Open, High, Low, Close, Volume].
    """
    start = start_date
    end = end_date

    all_data = {}
    failed = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        print(f"Downloading batch {i // batch_size + 1} "
              f"({len(batch)} tickers: {batch[0]}..{batch[-1]})")
        try:
            df = yf.download(
                batch,
                start=start,
                end=end,
                group_by="ticker",
                threads=True,
            )
            for ticker in batch:
                try:
                    if len(batch) == 1:
                        ticker_df = df.copy()
                    else:
                        ticker_df = df[ticker].copy()
                    ticker_df = ticker_df.dropna(how="all")
                    if not ticker_df.empty:
                        all_data[ticker] = ticker_df
                    else:
                        failed.append(ticker)
                except KeyError:
                    failed.append(ticker)
        except Exception as e:
            print(f"  Batch failed: {e}")
            failed.extend(batch)

    if failed:
        print(f"\nFailed to download {len(failed)} tickers: {failed[:20]}...")
    print(f"Successfully downloaded {len(all_data)} tickers.")
    return all_data


def save_data(all_data, data_dir=DATA_DIR):
    """Save each ticker's DataFrame as a CSV in the data directory."""
    os.makedirs(data_dir, exist_ok=True)
    for ticker, df in all_data.items():
        path = os.path.join(data_dir, f"{ticker}.csv")
        df.to_csv(path)
    print(f"Saved {len(all_data)} CSV files to {data_dir}/")


def load_data(data_dir=DATA_DIR):
    """Load all saved CSVs back into a dict of {ticker: DataFrame}."""
    all_data = {}
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".csv"):
            ticker = fname.replace(".csv", "")
            df = pd.read_csv(os.path.join(data_dir, fname), index_col=0, parse_dates=True)
            all_data[ticker] = df
    print(f"Loaded {len(all_data)} tickers from {data_dir}/")
    return all_data


if __name__ == "__main__":
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers from {TICKER_FILE}")
    all_data = download_data(tickers, start_date="2022-01-01", end_date="2025-01-01")
    save_data(all_data)
