def get_ai_analysis(headers, prev, current):
    """Аналитический разбор изменений через ChatGPT"""
    
    # Формируем читаемый список для ИИ: "Поле: было -> стало"
    changes = [f"{h}: {p} -> {c}" for h, p, c in zip(headers, prev, current)]
    changes_str = "\n".join(changes)

    prompt = f"""Ты — аналитик данных. Сравни показатели из Google Таблицы и дай короткий аналитический вывод.
    
    ДАННЫЕ:
    {changes_str}
    
    ЗАДАЧА:
    1. Проанализируй динамику (рост/падение/стабильность).
    2. Выдели критические изменения, если они есть.
    3. Сформулируй вывод одной-двумя емкими фразами в деловом стиле.
    Не перечисляй сухие цифры, сфокусируйся на смысле изменений."""
    
    response = client_ai.chat.completions.create(
        model="gpt-4o", # Рекомендую gpt-4o для более качественной аналитики
        messages=[{"role": "system", "content": "Ты профессиональный бизнес-аналитик."},
                  {"role": "user", "content": prompt}],
        temperature=0.7 # Добавляет немного вариативности в выводы
    )
    return response.choices.message.content

def monitor():
    sheet = gc.open_by_key(os.environ["SPREADSHEET_ID"])
    source_ws = sheet.get_worksheet(0)
    log_ws = sheet.get_worksheet(1)

    # Получаем заголовки и текущую строку данных
    headers = source_ws.row_values(1)[:5]
    current_row = source_ws.row_values(2)[:5]
    
    # Берем последнюю запись из лога для сравнения
    all_logs = log_ws.get_all_values()
    # Если лог пустой, считаем что данных не было
    prev_row = all_logs[-1][:5] if all_logs else ["0"] * 5

    if current_row != prev_row:
        # Получаем глубокий анализ
        analysis = get_ai_analysis(headers, prev_row, current_row)
        
        # Сохраняем во вторую таблицу: Дата | Данные | Анализ
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        log_ws.append_row([now] + current_row + [analysis])
        
        # Отправляем в Telegram
        send_tg(f"📊 **Анализ обновлений:**\n\n{analysis}")
