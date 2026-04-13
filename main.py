import os
import json
import gspread
import requests
from openai import OpenAI
from google.oauth2.service_account import Credentials
from datetime import datetime

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

    print("Telegram:", res.text)


# --- AI АНАЛИЗ ---
def get_ai_analysis(text):
    response = client_ai.responses.create(
        model="gpt-4.1-mini",
        input=text
    )
    return response.output_text


# --- РАСЧЕТ ПОКАЗАТЕЛЕЙ ---
def calculate_metrics(values):
    nums = [float(v) if v else 0 for v in values[:5]]

    total = sum(nums)
    avg = total / len(nums) if nums else 0

    return [round(total, 2), round(avg, 2)]


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
        log_ws = sheet.get_worksheet(1)

        raw_values = source_ws.row_values(2)
        metrics = calculate_metrics(raw_values)

        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        log_ws.append_row([now] + metrics)

        all_logs = log_ws.get_all_values()

        if len(all_logs) < 3:
            send_telegram("Недостаточно данных для сравнения")
            return

        headers = ["Сумма", "Среднее"]

        prev = all_logs[-2][1:]
        current = all_logs[-1][1:]

        # --- считаем проценты ---
        changes = []
        alerts = []

        for i in range(len(headers)):
            pct = percent_change(prev[i], current[i])

            arrow = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
            line = f"{headers[i]}: {prev[i]} → {current[i]} ({arrow} {pct}%)"
            changes.append(line)

            # 🚨 детект аномалий
            if abs(pct) >= 30:
                alerts.append(f"⚠️ Резкое изменение {headers[i]}: {pct}%")

        changes_text = "\n".join(changes)

        # --- AI анализ ---
        ai_prompt = f"""
Сделай краткий вывод по изменениям:

{changes_text}

1-2 предложения.
"""
        analysis = get_ai_analysis(ai_prompt)

        # --- финальное сообщение ---
        msg = f"📊 Отчет\n\n{changes_text}\n\n🧠 {analysis}"

        if alerts:
            alert_text = "\n".join(alerts)
            msg = f"🚨 ВНИМАНИЕ!\n{alert_text}\n\n" + msg

        send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()
