import os
import json
import gspread
import requests
from openai import OpenAI
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1. Настройка API
try:
    # OpenAI
    client_ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    
    # Google Sheets
    scope = ["https://google.com", "https://googleapis.com"]
    creds_dict = json.loads(os.environ["G_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gc = gspread.authorize(creds)
except KeyError as e:
    print(f"Ошибка: Не найден секрет {e}")
    exit(1)

def get_ai_analysis(headers, prev, current):
    """Генерация аналитического вывода через ChatGPT"""
    changes = [f"{h}: было {p} -> стало {c}" for h, p, c in zip(headers, prev, current)]
    changes_str = "\n".join(changes)

    prompt = f"""Ты — бизнес-аналитик. Сравни изменения в 5 ключевых показателях и дай краткий аналитический вывод.
    
    ИЗМЕНЕНИЯ:
    {changes_str}
    
    ЗАДАЧА:
    1. Оцени динамику (что выросло, что упало).
    2. Сформулируй главный вывод (1-2 предложения) в деловом стиле. 
    Избегай простого перечисления цифр, пиши про смысл (например: 'Эффективность упала из-за роста затрат')."""
    
    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Ты эксперт по анализу данных. Пиши кратко и по делу."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices.message.content

def send_telegram(text):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["CHAT_ID"]
    url = f"https://telegram.org{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

def main():
    print("Подключение к таблице...")
    sheet = gc.open_by_key(os.environ["SPREADSHEET_ID"])
    source_ws = sheet.get_worksheet(0)
    log_ws = sheet.get_worksheet(1)

    print("Чтение данных...")
    headers = source_ws.row_values(1)[:5]
    current_values = source_ws.row_values(2)[:5]
    print(f"Текущие данные: {current_values}")
    
    all_logs = log_ws.get_all_values()
    if not all_logs:
        prev_values = ["0"] * 5
        print("Лог пуст, используем начальные значения.")
    else:
        prev_values = all_logs[-1][1:6]
        print(f"Предыдущие данные из лога: {prev_values}")

    if current_values != prev_values:
        print("Данные изменились! Запрашиваю анализ у ИИ...")
        analysis = get_ai_analysis(headers, prev_values, current_values)
        print(f"Анализ готов: {analysis[:50]}...")
        
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        log_ws.append_row([now] + current_values + [analysis])
        print("Запись в таблицу добавлена.")
        
        send_telegram(f"📊 *Аналитический отчет*\n\n{analysis}")
        print("Сообщение в Telegram отправлено.")
    else:
        print("Данные не менялись. Скрипт завершен.")


if __name__ == "__main__":
    main()
