import pandas as pd

def compare_csvs(file1, file2, ignore_columns=None):
    # Load CSV files
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    # Drop ignored columns
    if ignore_columns:
        df1 = df1.drop(columns=ignore_columns, errors='ignore')
        df2 = df2.drop(columns=ignore_columns, errors='ignore')

    # Sort columns so comparison isn't affected by column order
    df1 = df1.reindex(sorted(df1.columns), axis=1)
    df2 = df2.reindex(sorted(df2.columns), axis=1)

    # Reset index
    df1 = df1.reset_index(drop=True)
    df2 = df2.reset_index(drop=True)

    # Check shape first
    if df1.shape != df2.shape:
        print("⚠️ DataFrames have different shapes after ignoring columns.")
        print(f"File1 shape: {df1.shape}, File2 shape: {df2.shape}")

    # Compare and show differences
    if df1.equals(df2):
        print("✅ CSV files match (ignoring specified columns).")
    else:
        print("❌ CSV files do not match. Differences below:")
        diff = df1.compare(df2)
        print(diff)

# === Usage ===
file1 = "h/VSCode/chf_data_ingestion/sourcefiles/CIS_Benchmark_Windows2022_Baseline_1_0_REST_NPE_2025-07-02.csv"
file2 = "h/VSCode/chf_data_ingestion/roles/azure_dsc_scans/files/ssc_azure_sourcefiles/CIS_Benchmark_Windows2022_Baseline_1_0_OPTIMISED_NPE_2025-07-02.csv"

# Call the function with column names you want to ignore
compare_csvs(file1, file2, ignore_columns=["LastChecked", "Timestamp"])
