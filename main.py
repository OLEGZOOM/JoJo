import logging
import random
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

START_BALANCE = 1000
DB_NAME = 'casino.db'

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
GREEN_NUMBERS = {0}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER)''')
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row is None:
        c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, START_BALANCE))
        conn.commit()
        balance = START_BALANCE
    else:
        balance = row[0]
    conn.close()
    return balance

def update_balance(user_id, new_balance):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
    conn.commit()
    conn.close()

def process_bet(bet_type, bet_value, bet_amount, number):
    if bet_type == 'number':
        if int(bet_value) == number:
            return bet_amount * 35, 35
    elif bet_type == 'color':
        color = 'green' if number == 0 else ('red' if number in RED_NUMBERS else 'black')
        if bet_value == color:
            return bet_amount * 1, 1
    elif bet_type == 'parity':
        if number == 0:
            return 0, 0
        parity = 'even' if number % 2 == 0 else 'odd'
        if bet_value == parity:
            return bet_amount * 1, 1
    elif bet_type == 'dozen':
        if number == 0:
            return 0, 0
        if 1 <= number <= 12 and bet_value == '1st12':
            return bet_amount * 2, 2
        elif 13 <= number <= 24 and bet_value == '2nd12':
            return bet_amount * 2, 2
        elif 25 <= number <= 36 and bet_value == '3rd12':
            return bet_amount * 2, 2
    return 0, 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    await update.message.reply_text(
        f"🎰 Добро пожаловать в казино Рулетка!\nВаш баланс: {balance} кредитов.\n\n"
        "Доступные команды:\n/balance - текущий баланс\n/bet <сумма> <тип> <значение> - сделать ставку\n/help - справка\n\n"
        "Примеры ставок:\n/bet 10 number 5  (ставка на число 5)\n/bet 5 color red  (ставка на красное)\n"
        "/bet 20 parity even  (ставка на чётное)\n/bet 15 dozen 2nd12  (ставка на вторую дюжину)"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Правила игры:\nВы делаете ставку, выбирая тип и значение. Затем бот крутит рулетку (0-36).\n"
        "Выигрыш зависит от типа ставки:\n• Число (0-36) — x35\n• Цвет (red, black, green) — x1\n"
        "• Чёт/нечет (even, odd) — x1 (зеро проигрывает)\n• Дюжина (1st12, 2nd12, 3rd12) — x2 (зеро проигрывает)\n\n"
        "Команды:\n/balance — показать баланс\n/bet сумма тип значение — сделать ставку"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    await update.message.reply_text(f"💰 Ваш текущий баланс: {balance} кредитов.")

async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("❌ Неправильный формат. Пример: /bet 10 number 5")
        return
    try:
        amount = int(args[0])
        bet_type = args[1].lower()
        bet_value = args[2].lower()
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом.")
        return
    if amount <= 0:
        await update.message.reply_text("❌ Сумма ставки должна быть положительной.")
        return
    balance = get_balance(user_id)
    if amount > balance:
        await update.message.reply_text(f"❌ Недостаточно средств. Ваш баланс: {balance}")
        return
    valid = False
    if bet_type == 'number':
        try:
            num = int(bet_value)
            if 0 <= num <= 36:
                valid = True
        except:
            pass
    elif bet_type == 'color':
        if bet_value in ('red', 'black', 'green'):
            valid = True
    elif bet_type == 'parity':
        if bet_value in ('even', 'odd'):
            valid = True
    elif bet_type == 'dozen':
        if bet_value in ('1st12', '2nd12', '3rd12'):
            valid = True
    else:
        await update.message.reply_text("❌ Неизвестный тип ставки. Допустимые: number, color, parity, dozen")
        return
    if not valid:
        await update.message.reply_text("❌ Неправильное значение для данного типа ставки.")
        return
    new_balance = balance - amount
    update_balance(user_id, new_balance)
    result_number = random.randint(0, 36)
    result_color = 'green' if result_number == 0 else ('red' if result_number in RED_NUMBERS else 'black')
    win, multiplier = process_bet(bet_type, bet_value, amount, result_number)
    message = f"🎲 Выпало число: {result_number} ({result_color})\n"
    if win > 0:
        new_balance = new_balance + win
        update_balance(user_id, new_balance)
        message += f"✅ Вы выиграли {win} кредитов (x{multiplier})!\n"
    else:
        message += f"❌ К сожалению, вы проиграли {amount} кредитов.\n"
    message += f"💰 Текущий баланс: {new_balance}"
    await update.message.reply_text(message)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    init_db()
    TOKEN = '8744772399:AAEoiIaut4i1jc7Jt5WGl4tWH6vCuTIG7lA'
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("bet", bet))
    application.add_error_handler(error_handler)
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
