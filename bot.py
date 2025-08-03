import json
import re
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv


load_dotenv()

try:
    with open("itmo_programs.json", "r", encoding="utf-8") as f:
        PROGRAM_DATA = json.load(f)
    print("Successfully loaded program data.")
except FileNotFoundError:
    print(
        "Error: 'itmo_programs.json' not found. Please run the scraping script first."
    )
    exit()

BOT_TOKEN = os.getenv("BOT_TOKEN")


def get_program_key(text: str) -> str | None:
    text_lower = text.lower()
    if "product" in text_lower or "продукт" in text_lower or "управление" in text_lower:
        return "ai_product"
    if (
        "ai" in text_lower
        or "искусственный интеллект" in text_lower
        or "инженер" in text_lower
    ):
        return "ai"
    return None


def get_semester(text: str) -> int | None:
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Привет! Я чат-бот для абитуриентов магистратуры ИТМО.\n\n"
        "Я могу помочь вам выбрать между двумя программами: 'Искусственный интеллект' (AI) и 'Управление ИИ-продуктами' (AI Product).\n\n"
        "Вот что вы можете спросить:\n"
        "✅ 'Какие курсы есть на программе AI в 1 семестре?'\n"
        "✅ 'В чем разница между программами?'\n"
        "✅ 'Посоветуй курсы, если мой бэкграунд - управление проектами и немного python.'\n\n"
        "Задайте свой вопрос!"
    )
    await update.message.reply_text(welcome_text)


def handle_list_courses(text: str) -> str:
    program_key = get_program_key(text)
    if not program_key:
        return "Пожалуйста, уточните, какая программа вас интересует: 'AI' или 'AI Product'?"

    program_info = PROGRAM_DATA.get(program_key, {})
    program_name = program_info.get("program_name", program_key)
    courses = program_info.get("courses", [])

    semester = get_semester(text)

    if semester is None:
        return f"Не нашел курсов для {semester}-го семестра в программе '{program_name}'. Попробуйте другой семестр."

    if semester:
        # Filter courses by the specified semester
        filtered_courses = [
            c for c in courses if str(semester) in c["semester"].split(", ")
        ]
        if not filtered_courses:
            return f"Не нашел курсов для {semester}-го семестра в программе '{program_name}'. Попробуйте другой семестр."

        response_lines = [
            f"📚 Курсы для {semester}-го семестра программы '{program_name}':\n"
        ]
        for course in filtered_courses:
            response_lines.append(f"- {course['name']} (*{course['credits']} з.е.*)")
        return "\n".join(response_lines)
    else:
        # List all courses if no semester is specified
        if not courses:
            return (
                f"Не удалось найти информацию о курсах для программы '{program_name}'."
            )

        response_lines = [f"📚 Все курсы программы '{program_name}':\n"]
        for course in courses:
            response_lines.append(f"- (Семестр {course['semester']}) {course['name']}")
        return "\n".join(response_lines)


def handle_recommendations(text: str) -> str:
    background_keywords = {
        "management": [
            "управлен",
            "менеджер",
            "менеджмент",
            "продукт",
            "product",
            "бизнес",
        ],
        "development": [
            "python",
            "c++",
            "web",
            "программист",
            "разработчик",
            "backend",
            "back-end",
            "frontend",
            "front-end",
            "full-stack",
            "fullstack",
            "full stack",
            "инженер",
            "developer",
            "engineer",
            "js",
            "javascript",
        ],
        "data_science": [
            "data science",
            "анализ данных",
            "статистика",
            "машинное обучение",
            "mlops",
            "ml",
            "мо",
        ],
        "design": ["дизайн", "интерфейс", "ui", "ux", "ux/ui"],
    }

    matched_skills = set()
    for skill, keywords in background_keywords.items():
        if any(keyword in text.lower() for keyword in keywords):
            matched_skills.add(skill)

    if not matched_skills:
        return "Не смог определить ваши навыки. Попробуйте описать свой бэкграунд, используя ключевые слова, например: 'менеджер', 'python', 'анализ данных'."

    recommendations = []
    all_courses = PROGRAM_DATA["ai"]["courses"] + PROGRAM_DATA["ai_product"]["courses"]

    for course in all_courses:
        score = 0
        course_lower = course["name"].lower()
        if "management" in matched_skills and any(
            kw in course_lower for kw in ["управлен", "продукт", "бизнес", "монетизац"]
        ):
            score += 1
        if "development" in matched_skills and any(
            kw in course_lower
            for kw in ["python", "разработк", "инженер", "программирован"]
        ):
            score += 1
        if "data_science" in matched_skills and any(
            kw in course_lower
            for kw in ["данны", "машин", "анализ", "статистик", "модели"]
        ):
            score += 1
        if "design" in matched_skills and any(
            kw in course_lower for kw in ["дизайн", "интерфейс"]
        ):
            score += 1

        if score > 0:
            recommendations.append((score, course))

    # Sort by score (highest first) and remove duplicates
    recommendations.sort(key=lambda x: x[0], reverse=True)
    unique_recs = list({rec["name"]: rec for score, rec in recommendations}.values())

    if not unique_recs:
        return "Не нашел подходящих курсов. Попробуйте переформулировать свой запрос."

    response_lines = [
        "✅ Основываясь на вашем бэкграунде, вам могут быть интересны следующие курсы:\n"
    ]
    for course in unique_recs[:5]:  # Show top 5
        prog_key = (
            "ai_product" if course in PROGRAM_DATA["ai_product"]["courses"] else "ai"
        )
        prog_name = PROGRAM_DATA[prog_key]["program_name"]
        response_lines.append(f"- {course['name']} (из программы *{prog_name}*)")

    return "\n".join(response_lines)


def handle_comparison(text: str) -> str:
    return (
        "Ключевое различие между программами:\n\n"
        "👨‍💻 *Искусственный интеллект (AI)* — это глубоко техническая программа для будущих ML-инженеров, исследователей и разработчиков. "
        "Фокус на алгоритмах, моделях, программировании и MLOps.\n"
        "Примеры курсов: `Вычисления на GPU`, `Технологии и практики MLOps`, `Алгоритмы и структуры данных`.\n\n"
        "📈 *Управление ИИ-продуктами (AI Product)* — программа для будущих продакт-менеджеров, которые будут руководить созданием и развитием AI-решений. "
        "Фокус на исследованиях, бизнес-моделях, управлении командой и продуктовой стратегии.\n"
        "Примеры курсов: `Стратегический продуктовый менеджмент`, `Монетизация ИИ-продуктов`, `Метрики и аналитика продукта`.\n\n"
        "Проще говоря, первая программа учит *как создавать AI*, а вторая — *что создавать и как на этом заработать*."
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    text_lower = text.lower()

    # Simple Intent Routing
    if any(k in text_lower for k in ["сравни", "разниц", "отлич", "что лучше"]):
        response = handle_comparison(text_lower)
    elif any(
        k in text_lower for k in ["рекоменд", "посоветуй", "бэкграунд", "background"]
    ):
        response = handle_recommendations(text_lower)
    elif "курс" in text_lower:
        response = handle_list_courses(text_lower)
    else:
        response = "Я не совсем понял ваш вопрос. Нажмите /start, чтобы увидеть примеры того, что я умею."

    await update.message.reply_markdown(response)


def main():
    print("Starting bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Start polling
    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
