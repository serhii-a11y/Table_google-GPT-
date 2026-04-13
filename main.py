import os
import json
import gspread
import requests
from openai import OpenAI
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. Настройка API
try:
    client_ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    
    scopes = [
        "https://googleapis.com",
        "https://googleapis.com"
    ]
    
    creds_info = json.loads(os.environ["G_JSON"])
    if "private_key" in creds_info:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
    # Измененный способ авторизации через service_account
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    
    # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ТОКЕНА
    from google.auth.transport.requests import Request
    creds.refresh(Request()) 
    
    gc = gspread.authorize(creds)
    print("Авторизация прошла успешно")
except Exception as e:
    print(f"Ошибка инициализации: {e}")
    exit(1)


def get_ai_analysis(headers, prev, current):
    """Генерация вывода через ChatGPT"""
    changes = [f"{h}: было {p} -> стало {c}" for h, p, c in zip(headers, prev, current)]
    changes_str = "\n".join(changes)

    prompt = f"""Ты бизнес-аналитик. Сравни показатели и дай краткий вывод.
    ДАННЫЕ:
    {changes_str}
    Напиши 1-2 предложения о сути изменений, без лишних цифр."""
    
    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices.message.content

def main():
    try:
        sheet = gc.open_by_key(os.environ["SPREADSHEET_ID"])
        source_ws = sheet.get_worksheet(0) # Лист с данными
        log_ws = sheet.get_worksheet(1)    # Лист для логов

        headers = source_ws.row_values(1)[:5]
        current_values = source_ws.row_values(2)[:5]
        
        all_logs = log_ws.get_all_values()
        prev_values = all_logs[-1][1:6] if all_logs else ["0"] * 5

        if current_values != prev_values:
            print("Данные изменились, запрашиваю анализ...")
            analysis = get_ai_analysis(headers, prev_values, current_values)
            
            now = datetime.now().strftime("%d.%m.%Y %H:%M")
            log_ws.append_row([now] + current_values + [analysis])
            
            # Отправка в Telegram
            token = os.environ["TELEGRAM_TOKEN"]
            chat_id = os.environ["CHAT_ID"]
            msg = f"📊 *Аналитический отчет*\n\n{analysis}"
            requests.post(f"https://telegram.org{token}/sendMessage", 
                          json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
            print("Отчет отправлен успешно")
        else:
            print("Изменений в данных не обнаружено")
            
    except Exception as e:
        print(f"Ошибка при работе с таблицей: {e}")
        exit(1)

if __name__ == "__main__":
    main()
