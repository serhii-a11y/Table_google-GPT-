import os
import json
import gspread
import requests
from openai import OpenAI
from google.oauth2.service_account import Credentials

# --- НАСТРОЙКА ---
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


# --- TELEGRAM ---
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


# --- AI АНАЛИЗ ---
def get_ai_analysis(text):
    try:
        response = client_ai.responses.create(
            model="gpt-4.1-mini",
            input=text
        )
        return response.output_text
    except Exception as e:
        return f"(AI ошибка: {e})"


# --- % РАЗНИЦА ---
def percent_change(old, new):
    try:
        old = float(old)
        new = float(new)

        if old == 0:
            return 0

        return round((new - old) / old * 100, 2)
    except:
        return 0


# --- ОСНОВНАЯ ЛОГИКА ---
def main():
    try:
        sheet = gc.open_by_key(os.environ["SPREADSHEET_ID"])
        source_ws = sheet.get_worksheet(0)

        # 📥 ЧИТАЕМ ВСЮ ТАБЛИЦУ
        all_data = source_ws.get_all_values()

        if len(all_data) < 3:
            send_telegram("❗ Недостаточно данных (нужно минимум 2 строки)")
            return

        headers = all_data[0]      # заголовки
        prev = all_data[-2]        # предпоследняя строка
        current = all_data[-1]     # последняя строка

        changes = []
        alerts = []

        # 🔍 СРАВНЕНИЕ
        for i in range(len(headers)):
            old = prev[i] if i < len(prev) else "0"
            new = current[i] if i < len(current) else "0"

            pct = percent_change(old, new)

            arrow = "📈" if pct > 0 else "📉" if pct < 0 else "➖"

            line = f"{headers[i]}: {old} → {new} ({arrow} {pct}%)"
            changes.append(line)

            # 🚨 ДЕТЕКТ СИЛЬНЫХ ИЗМЕНЕНИЙ
            if abs(pct) >= 30:
                alerts.append(f"⚠️ {headers[i]} изменился на {pct}%")

        changes_text = "\n".join(changes)

        # --- AI АНАЛИЗ ---
        ai_prompt = f"""
Сравни показатели и дай краткий вывод:

{changes_text}

1-2 предложения без лишних цифр.
"""
        analysis = get_ai_analysis(ai_prompt)

        # --- ФИНАЛЬНОЕ СООБЩЕНИЕ ---
        msg = f"📊 Отчет\n\n{changes_text}\n\n🧠 {analysis}"

        if alerts:
            alert_text = "\n".join(alerts)
            msg = f"🚨 ВНИМАНИЕ!\n{alert_text}\n\n" + msg

        send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Ошибка: {e}")
        print("Ошибка:", e)


if __name__ == "__main__":
    main()
