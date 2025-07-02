import pandas as pd

def compare_excels(file1, file2, sheet_name=0, ignore_columns=None):
    # Load the Excel files
    df1 = pd.read_excel(file1, sheet_name=sheet_name)
    df2 = pd.read_excel(file2, sheet_name=sheet_name)

    # Drop ignored columns
    if ignore_columns:
        df1 = df1.drop(columns=ignore_columns, errors='ignore')
        df2 = df2.drop(columns=ignore_columns, errors='ignore')

    # Reset index for reliable row-by-row comparison
    df1 = df1.reset_index(drop=True)
    df2 = df2.reset_index(drop=True)

    # Check shape
    if df1.shape != df2.shape:
        print("DataFrames have different shapes after ignoring columns.")
        print(f"File1 shape: {df1.shape}, File2 shape: {df2.shape}")

    # Compare row by row
    comparison = df1.equals(df2)

    if comparison:
        print("✅ Excel files match (ignoring specified columns).")
    else:
        print("❌ Excel files do not match.")
        # Show differences
        diff_df = df1.compare(df2)
        print("Differences:")
        print(diff_df)

# Example usage:
compare_excels(
    "file1.xlsx",
    "file2.xlsx",
    ignore_columns=["Timestamp", "LastUpdated"]
)
