import pandas as pd

def calculate_model_kpi(df):

    grouped = df.groupby("model").agg(
        revenue=("amount", "sum"),
        transactions=("amount", "count"),
        avg_check=("amount", "mean")
    ).reset_index()

    grouped["volume_power"] = grouped["revenue"] / grouped["transactions"]

    return grouped.sort_values("revenue", ascending=False)