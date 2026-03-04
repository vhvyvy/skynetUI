"""
Премиум-стили: анимации, градиенты, glassmorphism.
"""
import streamlit as st


def inject_premium_css():
    """Инжектирует кастомный CSS для премиального вида."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Базовые переменные */
    :root {
        --accent: #00d4aa;
        --accent-dim: rgba(0, 212, 170, 0.15);
        --glass: rgba(30, 41, 59, 0.7);
        --glass-border: rgba(255, 255, 255, 0.08);
        --shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        --radius: 12px;
        --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* Основной контейнер — тёмный градиент */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        background-attachment: fixed;
    }

    [data-testid="stHeader"] {
        background: rgba(15, 23, 42, 0.8);
        backdrop-filter: blur(12px);
    }

    /* Сайдбар */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%);
        border-right: 1px solid var(--glass-border);
    }

    /* Метрики — карточки с анимацией */
    [data-testid="stMetric"] {
        background: var(--glass);
        backdrop-filter: blur(12px);
        padding: 1rem 1.25rem;
        border-radius: var(--radius);
        border: 1px solid var(--glass-border);
        box-shadow: var(--shadow);
        transition: transform var(--transition), box-shadow var(--transition);
        animation: fadeInUp 0.5s ease-out forwards;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0, 212, 170, 0.1);
        border-color: rgba(0, 212, 170, 0.2);
    }
    [data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-weight: 500 !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-weight: 700 !important;
        font-size: 1.5rem !important;
    }

    /* Заголовки */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        color: #f8fafc !important;
        letter-spacing: -0.02em;
    }
    h1 { font-size: 1.9rem !important; }
    h2 { font-size: 1.4rem !important; }

    /* Табы — премиальный вид */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(30, 41, 59, 0.5);
        padding: 0.5rem;
        border-radius: var(--radius);
        border: 1px solid var(--glass-border);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        transition: all var(--transition);
    }
    .stTabs [aria-selected="true"] {
        background: var(--accent-dim) !important;
        color: var(--accent) !important;
        border: 1px solid rgba(0, 212, 170, 0.3);
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.05);
    }

    /* Кнопки */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all var(--transition);
        border: 1px solid var(--glass-border);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 212, 170, 0.2);
        border-color: var(--accent);
    }

    /* Селектбокс, инпуты */
    [data-testid="stSelectbox"] > div,
    [data-testid="stNumberInput"] > div {
        border-radius: 8px;
        transition: var(--transition);
    }
    [data-testid="stSelectbox"] > div:focus-within,
    [data-testid="stNumberInput"] > div:focus-within {
        box-shadow: 0 0 0 2px var(--accent-dim);
    }

    /* Разделитель — градиент */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--glass-border), transparent);
        margin: 1.5rem 0;
    }

    /* Экспандеры */
    .streamlit-expanderHeader {
        border-radius: 8px;
        transition: var(--transition);
    }
    .streamlit-expanderHeader:hover {
        background: rgba(255, 255, 255, 0.03);
    }

    /* DataFrames */
    [data-testid="stDataFrame"] {
        border-radius: var(--radius);
        overflow: hidden;
        box-shadow: var(--shadow);
        border: 1px solid var(--glass-border);
    }

    /* Caption, info */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: #94a3b8 !important;
    }

    /* Анимации */
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Сглаживание скролла */
    html {
        scroll-behavior: smooth;
    }

    /* Предупреждения и успех — softer */
    [data-testid="stAlert"] {
        border-radius: 8px;
        border: 1px solid var(--glass-border);
    }
    </style>
    """, unsafe_allow_html=True)
