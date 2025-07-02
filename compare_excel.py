import pandas as pd

def find_common_rows(file1, file2, ignore_columns=None):
    # Load CSVs
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    # Drop ignored columns
    if ignore_columns:
        df1 = df1.drop(columns=ignore_columns, errors='ignore')
        df2 = df2.drop(columns=ignore_columns, errors='ignore')

    # Sort columns alphabetically for consistent comparison
    df1 = df1.reindex(sorted(df1.columns), axis=1)
    df2 = df2.reindex(sorted(df2.columns), axis=1)

    # Remove duplicate rows in each individually (optional)
    df1 = df1.drop_duplicates()
    df2 = df2.drop_duplicates()

    # Find common rows
    common = pd.merge(df1, df2, how='inner')

    print(f"✅ Found {len(common)} common (duplicate) rows between files.")
    if not common.empty:
        print("🔍 Sample duplicates:")
        print(common.head())

    # Optional: Save to file
    # common.to_csv("common_rows.csv", index=False)

# === Example usage ===
file1 = "h/VSCode/chf_data_ingestion/sourcefiles/CIS_Benchmark_Windows2022_Baseline_1_0_REST_NPE_2025-07-02.csv"
file2 = "h/VSCode/chf_data_ingestion/roles/azure_dsc_scans/files/ssc_azure_sourcefiles/CIS_Benchmark_Windows2022_Baseline_1_0_OPTIMISED_NPE_2025-07-02.csv"

# Ignore columns that can vary but aren't meaningful for duplication check
ignore_cols = ["Timestamp", "LastChecked"]

find_common_rows(file1, file2, ignore_columns=ignore_cols)
