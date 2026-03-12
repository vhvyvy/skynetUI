"""
AI-анализ через OpenAI. Использует gpt-4o с полным контекстом данных.
API-ключ: st.secrets["openai_api_key"] или OPENAI_API_KEY из .env
"""
import os
import streamlit as st
from openai import OpenAI


def _get_api_key():
    """Получает API-ключ: сначала secrets.toml, потом .env"""
    key = None
    try:
        key = st.secrets.get("openai_api_key") or st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    if not key:
        key = os.getenv("OPENAI_API_KEY")
    return key


def chat_with_context(context: str, user_message: str, messages_history: list = None) -> str:
    """
    Отправляет запрос в GPT-4o с полным контекстом данных.
    messages_history: список {role, content} для продолжения диалога.
    """
    api_key = _get_api_key()
    if not api_key:
        return "Ошибка: не найден OpenAI API ключ. Добавьте OPENAI_API_KEY в .env или openai_api_key в .streamlit/secrets.toml"

    client = OpenAI(api_key=api_key)

    system_content = (
        "Ты — финансовый директор и аналитик OnlyFans агентства. "
        "У тебя есть полный доступ ко всем данным: транзакции, расходы, метрики, планы по моделям, "
        "KPI чаттеров (PPV Open Rate, APV, RPC, Conversion Score и др.), структура модель×чаттер, сравнение месяцев. "
        "Отвечай конкретно, с цифрами и выводами. Предлагай управленческие рекомендации."
    )

    msgs = [{"role": "system", "content": system_content}]

    if messages_history:
        for m in messages_history:
            msgs.append({"role": m["role"], "content": m["content"]})

    # Контекст вставляем в первый user message или отдельным сообщением
    full_context = f"=== ДАННЫЕ СИСТЕМЫ ===\n{context}\n\n=== ВОПРОС ===\n{user_message}"
    msgs.append({"role": "user", "content": full_context})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=msgs,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка OpenAI: {str(e)}"


def chat_with_context_stream(context: str, user_message: str, messages_history: list = None):
    """
    Стриминг-версия: отдаёт ответ по мере получения от API.
    yield-генератор для st.write_stream — пользователь видит текст сразу.
    """
    api_key = _get_api_key()
    if not api_key:
        yield "Ошибка: не найден OpenAI API ключ. Добавьте OPENAI_API_KEY в .env или openai_api_key в .streamlit/secrets.toml"
        return

    client = OpenAI(api_key=api_key)
    system_content = (
        "Ты — финансовый директор и аналитик OnlyFans агентства. "
        "У тебя есть полный доступ ко всем данным. Отвечай конкретно, с цифрами и выводами."
    )
    msgs = [{"role": "system", "content": system_content}]
    if messages_history:
        for m in messages_history:
            msgs.append({"role": m["role"], "content": m["content"]})
    full_context = f"=== ДАННЫЕ СИСТЕМЫ ===\n{context}\n\n=== ВОПРОС ===\n{user_message}"
    msgs.append({"role": "user", "content": full_context})

    try:
        stream = client.chat.completions.create(model="gpt-4o", messages=msgs, temperature=0.3, stream=True)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"Ошибка OpenAI: {str(e)}"
