import pandas as pd

def find_non_overlapping_rows(file1, file2, ignore_columns=None):
    # Load both CSV files
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    # Drop ignored columns
    if ignore_columns:
        df1 = df1.drop(columns=ignore_columns, errors='ignore')
        df2 = df2.drop(columns=ignore_columns, errors='ignore')

    # Sort columns to align structure
    df1 = df1.reindex(sorted(df1.columns), axis=1)
    df2 = df2.reindex(sorted(df2.columns), axis=1)

    # Remove duplicate rows within each file (optional)
    df1 = df1.drop_duplicates()
    df2 = df2.drop_duplicates()

    # Find rows in df1 that are NOT in df2
    only_in_df1 = pd.concat([df1, df2]).drop_duplicates(keep=False)
    only_in_df1 = only_in_df1.merge(df1, how='inner')

    # Find rows in df2 that are NOT in df1
    only_in_df2 = pd.concat([df2, df1]).drop_duplicates(keep=False)
    only_in_df2 = only_in_df2.merge(df2, how='inner')

    print(f"🔍 Rows in File 1 not in File 2: {len(only_in_df1)}")
    print(f"🔍 Rows in File 2 not in File 1: {len(only_in_df2)}")

    # Optional: Show samples
    if not only_in_df1.empty:
        print("\n📄 Sample rows only in File 1:")
        print(only_in_df1.head())

    if not only_in_df2.empty:
        print("\n📄 Sample rows only in File 2:")
        print(only_in_df2.head())

    # Optional: Save to files
    # only_in_df1.to_csv("only_in_file1.csv", index=False)
    # only_in_df2.to_csv("only_in_file2.csv", index=False)

# === Your file paths ===
file1 = "h/VSCode/chf_data_ingestion/sourcefiles/CIS_Benchmark_Windows2022_Baseline_1_0_REST_NPE_2025-07-02.csv"
file2 = "h/VSCode/chf_data_ingestion/roles/azure_dsc_scans/files/ssc_azure_sourcefiles/CIS_Benchmark_Windows2022_Baseline_1_0_OPTIMISED_NPE_2025-07-02.csv"

# === Ignore variable columns ===
ignore_cols = ["Timestamp", "LastChecked"]

find_non_overlapping_rows(file1, file2, ignore_columns=ignore_cols)
