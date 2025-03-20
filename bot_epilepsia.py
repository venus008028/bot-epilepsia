import telebot
from config import TELEGRAM_TOKEN 

bot= telebot.TeleBot("8076222487:AAGWJB_ihzJ8UY_4-xTrA1jNaHcxd_1iLPw")

@bot.message_handler(commands=['start', 'help'])
def start_message(message):     
    bot.reply_to(message, 'Hello, you are welcome to our bot')

bot.polling()