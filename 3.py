from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json

data_file = "data.json"
waiting_for_message = {}

# Загрузка данных
def load_data():
    try:
        with open(data_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"chats": {}, "reminders": {}, "groups": {}}




# Команда /forward
async def forward_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /forward <название_чата_или_группы>")
        return

    name = context.args[0]
    data = load_data()

    if name not in data['chats'] and name not in data['groups']:
        await update.message.reply_text(f"Чат или группа с именем '{name}' не найдены.")
        return

    waiting_for_message[update.message.chat_id] = name
    await update.message.reply_text(f"Теперь отправьте сообщение или медиа, которое нужно переслать в '{name}'.")

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if chat_id in waiting_for_message:
        name = waiting_for_message[chat_id]
        data = load_data()

        target_chat_ids = []
        if name in data['chats']:
            target_chat_ids = [data['chats'][name]]
        elif name in data['groups']:
            target_chat_ids = [data['chats'][chat] for chat in data['groups'][name] if chat in data['chats']]

        if not target_chat_ids:
            await update.message.reply_text(f"Не удалось найти чаты для '{name}'.")
            del waiting_for_message[chat_id]
            return

        # Если это группа медиа
        if update.message.media_group_id:
            media_group_id = update.message.media_group_id

            # Сохраняем все сообщения с одинаковым media_group_id
            media_messages = [update.message]

            # Ищем остальные сообщения в группе, которые могут прийти позже
            async def collect_media_group(update: Update):
                if update.message.media_group_id == media_group_id:
                    media_messages.append(update.message)

            context.application.add_handler(MessageHandler(filters.ALL, collect_media_group))

            # Делаем паузу, чтобы собрать все медиа в группе
            await context.application.job_queue.run_once(
                send_media_group, when=0.5, data={"media_group_id": media_group_id, "chat_id": chat_id, "name": name, "media_messages": media_messages}
            )
        else:
            # Пересылаем одиночное сообщение
            for target_chat_id in target_chat_ids:
                await update.message.forward(chat_id=target_chat_id)
            await update.message.reply_text(f"Сообщение переслано в '{name}'.")

        del waiting_for_message[chat_id]

# Отправка медиагруппы
async def send_media_group(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    media_group_id = job_data["media_group_id"]
    chat_id = job_data["chat_id"]
    name = job_data["name"]
    media_messages = job_data["media_messages"]

    target_chat_ids = []

    # Получаем список целевых чатов
    data = load_data()
    if name in data['chats']:
        target_chat_ids = [data['chats'][name]]
    elif name in data['groups']:
        target_chat_ids = [data['chats'][chat] for chat in data['groups'][name] if chat in data['chats']]

    # Пересылаем все сообщения медиагруппы
    for target_chat_id in target_chat_ids:
        for message in media_messages:
            await message.forward(chat_id=target_chat_id)

    # Уведомление пользователя
    await context.bot.send_message(chat_id=chat_id, text=f"Медиагруппа переслана в '{name}'.")

# Основная функция
def main():
    token = "7616320728:AAGpndwt_3K8Rq7SMq77UbyBccLabmKwJ78"
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("forward", forward_message_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()