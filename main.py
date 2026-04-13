import os
import json
import gspread
import requests
from openai import OpenAI
from google.oauth2.service_account import Credentials
from datetime import datetime

# Настройка
try:
    client_ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    
    # Современный способ авторизации
    try:
    scopes = ["https://googleapis.com", "https://googleapis.com"]
    creds_info = json.loads(os.environ["G_JSON"])
    
    # Исправление возможных проблем с переносом строки в ключе
    if "\\n" in creds_info["private_key"]:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)
except Exception as e:
    print(f"Ошибка инициализации JSON: {e}")
    exit(1)

def get_ai_analysis(headers, prev, current):
    changes = [f"{h}: {p} -> {c}" for h, p, c in zip(headers, prev, current)]
    prompt = f"Ты аналитик. Данные: {', '.join(changes)}. Напиши короткий вывод о динамике."
    
    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices.message.content

def main():
    try:
        sheet = gc.open_by_key(os.environ["SPREADSHEET_ID"])
        source_ws = sheet.get_worksheet(0)
        log_ws = sheet.get_worksheet(1)

        current_values = source_ws.row_values(2)[:5]
        headers = source_ws.row_values(1)[:5]
        
        all_logs = log_ws.get_all_values()
        prev_values = all_logs[-1][1:6] if all_logs else ["0"] * 5

        if current_values != prev_values:
            analysis = get_ai_analysis(headers, prev_values, current_values)
            now = datetime.now().strftime("%d.%m.%Y %H:%M")
            log_ws.append_row([now] + current_values + [analysis])
            
            # Отправка в ТГ
            msg = f"📊 *Аналитика:*\n\n{analysis}"
            requests.post(f"https://telegram.org{os.environ['TELEGRAM_TOKEN']}/sendMessage", 
                          json={"chat_id": os.environ["CHAT_ID"], "text": msg, "parse_mode": "Markdown"})
            print("Успех: Данные обновлены.")
        else:
            print("Изменений нет.")
            
    except Exception as e:
        print(f"Ошибка при работе с таблицей: {e}")
        exit(1)

if __name__ == "__main__":
    main()
