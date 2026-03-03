import pandas as pd
import calendar
from db import get_connection

conn = get_connection()

def load_transactions():
    df = pd.read_sql(
        "SELECT date, model, chatter, amount, shift_id FROM transactions",
        conn
    )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    df["month_label"] = df["date"].apply(
        lambda x: f"{calendar.month_name[int(x.month)]} {int(x.year)}"
    )

    return df