## convinient function to show Null and Distinct counts in all columns in the dataframe
def summarize_nulls(df, df_name):
    total_rows = len(df)
    null_count = df.isnull().sum()
    distinct_count = df.nunique()
    null_counts_summary = pd.DataFrame( {
        "Missing Values" : null_count,
        "Percentage": (null_count/total_rows * 100).round(2),
        "Distinct Values" : distinct_count,
        "Percentage Distinct of Non Missing" : (distinct_count/(total_rows-null_count) * 100).round(2),
        "Percentage Distinct" : (distinct_count/total_rows * 100).round(2),
        "Total Rows" : total_rows
    }).sort_values(by='Missing Values', ascending=False)
    print(f"Null counts in '{df_name}' by column (highest to lowest):")
    print(null_counts_summary)

#To show all data without truncation in any dimension
# pd.set_option('display.width', 300)
# pd.set_option('display.max_columns', None)
# pd.set_option('display.max_colwidth', None) 