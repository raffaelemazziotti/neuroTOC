import pandas as pd

def get_journal_info():
    # Replace with your Google Sheets URL and export it as CSV
    sheet_id = "1HIBPpTTpuznVZdr5Kf-hd6vp6iWYJQvjasnrmKv6p8w"
    sheet_name = "Foglio1"  # Adjust if the sheet name is different
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    # Read the sheet into a DataFrame
    df = pd.read_csv(url)

    return df
