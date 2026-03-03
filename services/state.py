import streamlit as st
from config import *

def init_state():

    defaults = {
        "chatter_pct": CHATTER_PCT,
        "model_pct": MODEL_PCT,
        "admin_pct": ADMIN_PCT,
        "withdrawal_pct": WITHDRAWAL_PCT,
        "retention_pct": RETENTION_PCT,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value