"""Data loader for stock and index data from Yahoo Finance."""

import yaml
import yfinance as yf
import pandas as pd
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STOCK_DIR = os.path.join(DATA_DIR, "stock")
INDEX_DIR = os.path.join(DATA_DIR, "index")
TICKER_FILE = os.path.join(os.path.dirname(__file__), "ticker.yaml")

# Index tickers to download
INDEX_TICKERS = ["^GSPC", "SPY"]  # S&P 500 index and ETF


def load_tickers(path=TICKER_FILE):
    """Load stock tickers from YAML file."""
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
    all_data = {}
    failed = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        print(f"Downloading batch {i // batch_size + 1} "
              f"({len(batch)} tickers: {batch[0]}..{batch[-1]})")
        try:
            df = yf.download(
                batch,
                start=start_date,
                end=end_date,
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


def download_index_data(tickers=INDEX_TICKERS, start_date="2022-01-01", end_date="2025-01-01"):
    """Download index data (S&P 500, SPY, etc.)."""
    print(f"Downloading index data: {tickers}")
    all_data = {}

    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date, end=end_date)
            if not df.empty:
                # Flatten MultiIndex columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                # Reorder columns to match stock data format
                df = df[["Open", "High", "Low", "Close", "Volume"]]
                all_data[ticker] = df
                print(f"  Downloaded {ticker}: {len(df)} rows")
            else:
                print(f"  {ticker}: no data")
        except Exception as e:
            print(f"  {ticker} failed: {e}")

    return all_data


def save_stock_data(all_data, data_dir=STOCK_DIR):
    """Save stock data to CSV files."""
    os.makedirs(data_dir, exist_ok=True)
    for ticker, df in all_data.items():
        path = os.path.join(data_dir, f"{ticker}.csv")
        df.to_csv(path)
    print(f"Saved {len(all_data)} stock CSV files to {data_dir}/")


def save_index_data(all_data, data_dir=INDEX_DIR):
    """Save index data to CSV files."""
    os.makedirs(data_dir, exist_ok=True)
    for ticker, df in all_data.items():
        # Replace special characters in filename
        safe_name = ticker.replace("^", "")
        path = os.path.join(data_dir, f"{safe_name}.csv")
        df.to_csv(path)
    print(f"Saved {len(all_data)} index CSV files to {data_dir}/")


def load_stock_data(data_dir=STOCK_DIR):
    """Load all stock CSVs into a dict of {ticker: DataFrame}."""
    all_data = {}
    if not os.path.exists(data_dir):
        print(f"Stock data directory not found: {data_dir}")
        return all_data

    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".csv"):
            ticker = fname.replace(".csv", "")
            df = pd.read_csv(os.path.join(data_dir, fname), index_col=0, parse_dates=True)
            all_data[ticker] = df
    print(f"Loaded {len(all_data)} stocks from {data_dir}/")
    return all_data


def load_index_data(data_dir=INDEX_DIR):
    """Load all index CSVs into a dict of {ticker: DataFrame}."""
    all_data = {}
    if not os.path.exists(data_dir):
        print(f"Index data directory not found: {data_dir}")
        return all_data

    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".csv"):
            ticker = fname.replace(".csv", "")
            df = pd.read_csv(os.path.join(data_dir, fname), index_col=0, parse_dates=True)
            all_data[ticker] = df
    print(f"Loaded {len(all_data)} indices from {data_dir}/")
    return all_data


# Backward compatibility
def save_data(all_data, data_dir=STOCK_DIR):
    """Backward compatible save function."""
    save_stock_data(all_data, data_dir)


def load_data(data_dir=STOCK_DIR):
    """Backward compatible load function."""
    return load_stock_data(data_dir)


if __name__ == "__main__":
    # Download stock data
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers from {TICKER_FILE}")

    # Uncomment to re-download stock data
    # stock_data = download_data(tickers, start_date="2022-01-01", end_date="2025-01-01")
    # save_stock_data(stock_data)

    # Download index data
    index_data = download_index_data(start_date="2022-01-01", end_date="2025-01-01")
    save_index_data(index_data)