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
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_info = json.loads(os.environ["G_JSON"])
    
    if "private_key" in creds_info:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)
    
    print("Авторизация прошла успешно")

except Exception as e:
    print(f"Ошибка инициализации: {e}")
    exit(1)


def send_telegram(msg):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["CHAT_ID"]

    res = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": msg
        }
    )

    print("Telegram response:", res.text)


def get_ai_analysis(headers, prev, current):
    changes = [f"{h}: было {p} -> стало {c}" for h, p, c in zip(headers, prev, current)]
    changes_str = "\n".join(changes)

    prompt = f"""Ты бизнес-аналитик. Сравни показатели и дай краткий вывод.
ДАННЫЕ:
{changes_str}
Напиши 1-2 предложения о сути изменений, без лишних цифр."""

    response = client_ai.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text


def pad(arr, n=5):
    return arr + [""] * (n - len(arr))


def main():
    try:
        sheet = gc.open_by_key(os.environ["SPREADSHEET_ID"])
        source_ws = sheet.get_worksheet(0)
        log_ws = sheet.get_worksheet(1)

        headers = pad(source_ws.row_values(1)[:5])
        current_values = pad(source_ws.row_values(2)[:5])
        
        all_logs = log_ws.get_all_values()

        if len(all_logs) > 1:
            prev_values = all_logs[-1][1:6]
        else:
            prev_values = ["0"] * 5

        # 🔥 ВСЕГДА отправляем (можно поменять на False)
        FORCE_SEND = True

        if current_values != prev_values or FORCE_SEND:
            print("Отправка отчета...")

            analysis = get_ai_analysis(headers, prev_values, current_values)
            
            now = datetime.now().strftime("%d.%m.%Y %H:%M")
            log_ws.append_row([now] + current_values + [analysis])

            msg = f"📊 Аналитический отчет\n\n{analysis}"
            send_telegram(msg)

            print("Отчет отправлен успешно")

        else:
            print("Изменений нет, но отправим статус")
            send_telegram("ℹ️ Данные без изменений")

    except Exception as e:
        print(f"Ошибка при работе с таблицей: {e}")
        send_telegram(f"❌ Ошибка: {e}")
        exit(1)


if __name__ == "__main__":
    main()
