"""
UI-компоненты: skeleton loader, bento layout, Lottie.
"""
import streamlit as st


def render_skeleton(rows=3, cols=4, key="skeleton"):
    """Рендерит skeleton loader как placeholder."""
    html = "<div style='display:flex;flex-direction:column;gap:0.75rem;'>"
    for _ in range(rows):
        html += "<div style='display:flex;gap:0.75rem;'>"
        for _ in range(cols):
            html += "<div class='skeleton' style='height:4rem;flex:1;'></div>"
        html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def load_lottie_url(url: str):
    """Загружает Lottie JSON по URL."""
    try:
        import requests
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# Lottie URLs (lottiefiles.com free)
LOTTIE_LOADING = "https://assets4.lottiefiles.com/packages/lf20_ymjgnjls.json"
LOTTIE_SUCCESS = "https://assets10.lottiefiles.com/packages/lf20_success.json"
LOTTIE_CHART = "https://assets2.lottiefiles.com/packages/lf20_u4yrau.json"


def st_lottie_safe(url: str, height=120, key=None):
    """Безопасный вызов st_lottie — если не установлен, ничего не рендерит."""
    try:
        from streamlit_lottie import st_lottie
        data = load_lottie_url(url)
        if data:
            st_lottie(data, height=height, key=key or f"lottie_{hash(url)}")
    except ImportError:
        pass
