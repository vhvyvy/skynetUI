import psycopg2
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )