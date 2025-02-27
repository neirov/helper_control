# coding: utf-8
import telebot
import logging
import datetime
import os
import sys
import subprocess
import time
from flask import Flask, request
import sqlite3
from threading import Timer
from telebot import types
import random

BOT_TOKEN = "6370204668:AAE8bXa4KdAVYQOJ66wURK7xFY21SzJW7Rg"
DATABASE_PATH = "E:\\Helper_bot\\bot_database.db" # Укажите имя файла вашей БД
CROSS_ZERO_DB_PATH = "E:\\Helper_bot\\cross_and_zero_database.db"
print(f"DATABASE_PATH = {DATABASE_PATH}")

def create_cross_zero_tables():
    try:
        conn = sqlite3.connect(CROSS_ZERO_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                board TEXT,
                current_player TEXT,
                player1_id INTEGER,
                player2_id INTEGER,
                PRIMARY KEY (chat_id, message_id)
            )
        ''')
        conn.commit()
        conn.close()
        print("Таблицы для крестиков-ноликов созданы/обновлены")
    except Exception as e:
        print(f"Ошибка при создании таблиц крестиков-ноликов: {e}")

bot = telebot.TeleBot(BOT_TOKEN)

# Время запуска бота
bot_start_time = datetime.datetime.now()

def is_message_old(message):
    message_time = datetime.datetime.fromtimestamp(message.date)
    return message_time < bot_start_time

def create_tables():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Таблица dev
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dev (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        print("Таблица dev создана/обновлена")  # Добавлено сообщение об успешном создании/обновлении

        # Таблица admins
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        print("Таблица admins создана/обновлена")  # Добавлено сообщение об успешном создании/обновлении

        # Таблица mutes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mutes (
                user_id INTEGER PRIMARY KEY,
                end_time TEXT,
                reason TEXT
            )
        ''')
        print("Таблица mutes создана/обновлена")  # Добавлено сообщение об успешном создании/обновлении

        # Таблица banned_users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT
            )
        ''')
        print("Таблица banned_users создана/обновлена")  # Добавлено сообщение об успешном создании/обновлении


        conn.commit()
        conn.close()
        print("Таблицы созданы (если их не было) и обновлены.")  # Добавлено сообщение об успешном создании/обновлении
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")

# Функция для получения уровня доступа пользователя из БД
def is_admin(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None  # True, если пользователь есть в таблице admins
    except Exception as e:
        print(f"Ошибка при проверке администратора: {e}")
        return False  # Считаем, что не администратор в случае ошибки

def is_dev(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM dev WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Ошибка при проверке разработчика: {e}")
        return False

def start_game(chat_id, player1_id, player2_id):
    try:
        conn = sqlite3.connect(CROSS_ZERO_DB_PATH)
        cursor = conn.cursor()
        board = [' '] * 9
        current_player = 'X'

        #  Отправляем сообщение, чтобы сохранить его ID
        message = bot.send_message(chat_id, "Подготовка игрового поля...")

        # Сохраняем ID сообщения в таблицу
        cursor.execute("INSERT OR REPLACE INTO games (chat_id, message_id, board, current_player, player1_id, player2_id) VALUES (?, ?, ?, ?, ?, ?)",
                       (chat_id, message.message_id, "".join(board), current_player, player1_id, player2_id))
        conn.commit()
        conn.close()
        return board, message.message_id
    except Exception as e:
        print(f"Ошибка при старте игры: {e}")
        return None, None

def get_game_state(chat_id, message_id):
    try:
        conn = sqlite3.connect(CROSS_ZERO_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT board, current_player, player1_id, player2_id FROM games WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))
        result = cursor.fetchone()
        conn.close()
        if result:
            board, current_player, player1_id, player2_id = result
            return list(board), current_player, player1_id, player2_id
        else:
            return None, None, None, None  # Игра не найдена
    except Exception as e:
        print(f"Ошибка при получении состояния игры: {e}")
        return None, None, None, None

def make_move(chat_id, message_id, position, player):
    try:
        conn = sqlite3.connect(CROSS_ZERO_DB_PATH)
        cursor = conn.cursor()
        board, current_player, player1_id, player2_id = get_game_state(chat_id, message_id)
        if board is None:
            conn.close()
            return None, "Игра не найдена."

        if current_player != player:
            conn.close()
            return board, "Сейчас ход другого игрока."

        if board[position] != ' ':
            conn.close()
            return board, "Эта клетка уже занята."

        board[position] = player
        current_player = 'O' if player == 'X' else 'X'
        cursor.execute("UPDATE games SET board = ?, current_player = ? WHERE chat_id = ? AND message_id = ?",
                       ("".join(board), current_player, chat_id, message_id))
        conn.commit()
        conn.close()
        return board, None  # None - означает, что ошибки нет
    except Exception as e:
        print(f"Ошибка при совершении хода: {e}")
        return None, "Произошла ошибка при совершении хода."

def check_winner(board):
    winning_combinations = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Columns
        (0, 4, 8), (2, 4, 6)               # Diagonals
    ]
    for combo in winning_combinations:
        if board[combo[0]] != ' ' and board[combo[0]] == board[combo[1]] == board[combo[2]]:
            return board[combo[0]]
    if ' ' not in board:
        return 'draw'
    return None

def get_board_markup(board, current_player, chat_id, message_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []  # Список для хранения кнопок
    for i in range(9):
        if board[i] == ' ':
            callback_data = f"move:{chat_id}:{message_id}:{i}:{current_player}"
            button_text = "·"  # Или любой другой символ, который хорошо отображается
        else:
            callback_data = f"no_move"
            button_text = board[i]  # Отображаем X или O на кнопке
        button = types.InlineKeyboardButton(button_text, callback_data=callback_data)
        buttons.append(button)

    # Добавляем кнопки в markup по 3 в ряд
    for i in range(0, 9, 3):
        markup.add(buttons[i], buttons[i+1], buttons[i+2])

    return markup

def get_player_symbol(chat_id, message_id, user_id):
    board, current_player, player1_id, player2_id = get_game_state(chat_id, message_id)
    if board is None:
        return None
    if user_id == player1_id:
        return 'X'
    elif user_id == player2_id:
        return 'O'
    return None

def get_current_message_id(chat_id):
     try:
        conn = sqlite3.connect(CROSS_ZERO_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT current_message_id FROM games WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        else:
            return None
     except Exception as e:
        print(f"Ошибка при получении current_message_id: {e}")
        return None
     
def update_current_message_id(chat_id, new_message_id):
    try:
        conn = sqlite3.connect(CROSS_ZERO_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE games SET current_message_id = ? WHERE chat_id = ?", (new_message_id, chat_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка при обновлении current_message_id: {e}")

def update_user_info_callback(call):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, chat_id, username, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (call.from_user.id, call.message.chat.id, call.from_user.username, call.from_user.first_name, call.from_user.last_name)
        )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка при обновлении информации о пользователе (callback): {e}")

def update_user_info_message(message):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, chat_id, username, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, message.chat.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка при обновлении информации о пользователе (message): {e}")

def update_user_info(message):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, chat_id, username, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, message.chat.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка при обновлении информации о пользователе: {e}")

# Команда /xo
@bot.message_handler(commands=['xo'])
def xo_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    update_user_info_message(message)

    if message.chat.type == 'private':
        bot.reply_to(message, "Эту команду можно использовать только в групповых чатах.")
        return

    opponent_id = None
    if message.reply_to_message:
        # Получаем ID из reply
        opponent_id = message.reply_to_message.from_user.id
    else:
        try:
            # Получаем ID из аргументов команды
            opponent_id = int(message.text.split()[1])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /xo <user_id> или сделайте reply на сообщение пользователя, с которым хотите играть.")
            return

    if opponent_id == user_id:
        bot.reply_to(message, "Нельзя играть самим с собой.")
        return

    if user_id == bot.get_me().id or opponent_id == bot.get_me().id:
        bot.reply_to(message, "Нельзя играть с ботом.")
        return

    # Получаем информацию об отправителе запроса
    try:
        user = bot.get_chat_member(chat_id, user_id).user
        player1_username = user.username
        player1_firstname = user.first_name
    except telebot.apihelper.ApiException as e:
        player1_username = "Игрок"
        player1_firstname = "Игрок"
        print(f"Не удалось получить информацию об отправителе: {e}")

    # Получаем информацию о противнике
    try:
        opponent = bot.get_chat_member(chat_id, opponent_id).user
        opponent_username = opponent.username
        opponent_firstname = opponent.first_name
    except telebot.apihelper.ApiException as e:
        bot.reply_to(message, "Не удалось найти пользователя с указанным ID.")
        print(f"Не удалось получить информацию о противнике: {e}")
        return

    # Создаем кнопки
    markup = types.InlineKeyboardMarkup(row_width=2)
    yes_button = types.InlineKeyboardButton("Да", callback_data=f"xo_accept:{user_id}:{opponent_id}:{chat_id}")
    no_button = types.InlineKeyboardButton("Нет", callback_data=f"xo_reject:{user_id}:{opponent_id}:{chat_id}")
    markup.add(yes_button, no_button)

    # Отправляем сообщение с запросом
    bot.send_message(
        chat_id,
        f"Игрок @{opponent_username} ({opponent_firstname}) \n@{player1_username} ({player1_firstname}) предлагает Вам начать игру в Крестики-Нолики.\nДля принятия решения нажмите на кнопки ниже:",
        reply_markup=markup
    )

@bot.message_handler(commands=['end_xo'])
def end_xo_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(user_id):
        bot.reply_to(message, "Эта команда доступна только администраторам.")
        return

    try:
        conn = sqlite3.connect(CROSS_ZERO_DB_PATH)
        cursor = conn.cursor()

        # Получаем информацию об игре
        cursor.execute("SELECT message_id FROM games WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()
        if result:
            message_id = result[0]

            # Удаляем информацию об игре из базы данных
            cursor.execute("DELETE FROM games WHERE chat_id = ?", (chat_id,))
            conn.commit()

            # Удаляем сообщение с игровым полем
            try:
                bot.delete_message(chat_id, message_id)
            except telebot.apihelper.ApiException as e:
                if "message to delete not found" in str(e):
                    pass  # Просто игнорируем ошибку, если сообщение не найдено
                else:
                    print(f"Не удалось удалить сообщение: {e}")  # Можно игнорировать

            bot.reply_to(message, "Игра прервана.")
        else:
            bot.reply_to(message, "В этом чате нет активной игры.")
        conn.close()

    except Exception as e:
        print(f"Ошибка при прерывании игры: {e}")
        bot.reply_to(message, "Произошла ошибка при прерывании игры.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('xo_'))
def xo_callback(call):
    try:
        action, user1_id, user2_id, chat_id = call.data.split(":")
        user1_id = int(user1_id)
        user2_id = int(user2_id)
        chat_id = int(chat_id)
        call_user_id = call.from_user.id # ID нажавшего на кнопку

        if action == 'xo_accept':
            if call_user_id == user2_id:  # Проверяем, что кнопку "Да" нажал правильный пользователь
                board, message_id = start_game(chat_id, user1_id, user2_id)
                if board is None:
                    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Не удалось начать игру.")
                    bot.answer_callback_query(call.id)
                    return

                try:
                     player1 = bot.get_chat_member(chat_id, user1_id).user.first_name
                except telebot.apihelper.ApiException as e:
                     player1 = "Игрок"
                     print(f"Не удалось получить имя первого игрока: {e}")
                player_symbol = 'X'
                markup = get_board_markup(board, player_symbol, chat_id, message_id)

                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"Игра началась! Ходит {player1} (X).", reply_markup=markup)

            else:
                bot.answer_callback_query(call.id, "Вы не можете принять этот запрос.")
                return

        elif action == 'xo_reject':
            if call_user_id == user2_id:  # Проверяем, что кнопку "Нет" нажал правильный пользователь
                 bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Запрос на игру отклонен.")
            else:
                bot.answer_callback_query(call.id, "Вы не можете отклонить этот запрос.")
                return

        bot.answer_callback_query(call.id)

    except Exception as e:
        print(f"Ошибка в xo_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка.")

def get_inventory(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT cucumber FROM inventory WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            cucumber = result[0]
            return {"cucumber": cucumber}  # Возвращаем словарь с предметами
        else:
            return {}  # Если пользователя нет в инвентаре, возвращаем пустой словарь
    except Exception as e:
        print(f"Ошибка при получении инвентаря: {e}")
        return {}

@bot.message_handler(commands=['inventory'])
def inventory_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    inventory = get_inventory(user_id)

    inventory_text = f"Инвентарь пользователя {first_name}:\n"
    if inventory:
        if inventory.get("cucumber", 0) > 0:
            inventory_text += f"\n 🥒 Кукумбер: {inventory['cucumber']}\n"
        # Добавляем другие предметы аналогично
    else:
        inventory_text += "Инвентарь пуст.\n"

    bot.reply_to(message, inventory_text)

@bot.message_handler(commands=['chat_connect'])
def chat_connect_command(message):
    chat_id = message.chat.id
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Проверяем, есть ли чат в базе данных
        cursor.execute("SELECT 1 FROM connected_chats WHERE chat_id = ?", (chat_id,))
        if cursor.fetchone():
            bot.reply_to(message, "Этот чат уже подключен.")
        else:
            # Добавляем ID чата в таблицу
            cursor.execute("INSERT INTO connected_chats (chat_id) VALUES (?)", (chat_id,))
            conn.commit()
            bot.reply_to(message, "Чат успешно подключен.")

        conn.close()
    except Exception as e:
        print(f"Ошибка при подключении чата: {e}")
        bot.reply_to(message, "Произошла ошибка при подключении чата.")

@bot.message_handler(commands=['chats'])
def chats_command(message):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Получаем список подключенных чатов
        cursor.execute("SELECT chat_id FROM connected_chats")
        connected_chats = cursor.fetchall()

        if not connected_chats:
            bot.reply_to(message, "Подключенных чатов нет.")
            conn.close()
            return

        chat_list_text = "Подключенные чаты:\n"
        for i, chat_data in enumerate(connected_chats):
            chat_id = chat_data[0]
            try:
                chat = bot.get_chat(chat_id)
                chat_name = chat.title if chat.title else chat.first_name + (f" {chat.last_name}" if chat.last_name else "") # Получаем название чата
            except telebot.apihelper.ApiException as e:
                chat_name = "Неизвестный чат"
                print(f"Ошибка при получении информации о чате {chat_id}: {e}")
            chat_list_text += f"{i+1}. {chat_name} ({chat_id})\n" # Форматируем вывод

        bot.reply_to(message, chat_list_text)
        conn.close()

    except Exception as e:
        print(f"Ошибка при получении списка чатов: {e}")
        bot.reply_to(message, "Произошла ошибка при получении списка чатов.")

@bot.message_handler(commands=['chat_delete'])
def chat_delete_command(message):
    chat_id = message.chat.id
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Проверяем, есть ли чат в базе данных
        cursor.execute("SELECT 1 FROM connected_chats WHERE chat_id = ?", (chat_id,))
        if not cursor.fetchone():
            bot.reply_to(message, "Этот чат не подключен.")
        else:
            # Удаляем ID чата из таблицы
            cursor.execute("DELETE FROM connected_chats WHERE chat_id = ?", (chat_id,))
            conn.commit()
            bot.reply_to(message, "Чат успешно удален.")

        conn.close()
    except Exception as e:
        print(f"Ошибка при удалении чата: {e}")
        bot.reply_to(message, "Произошла ошибка при удалении чата.")

@bot.message_handler(commands=['alert'])
def alert_command(message):
    user_id = message.from_user.id  # Айди пользователя, отправившего команду
    username = message.from_user.username  # Получаем юзернейм

    if not is_dev(user_id):
        bot.reply_to(message, "Эта команда доступна только разработчикам.")
        return

    alert_text = message.text[6:].strip()  # Получаем текст сообщения, убирая "/alert" и пробелы

    if not alert_text:
        bot.reply_to(message, "Пожалуйста, укажите текст сообщения после команды /alert.")
        return

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Получаем список подключенных чатов
        cursor.execute("SELECT chat_id FROM connected_chats")
        connected_chats = cursor.fetchall()

        if not connected_chats:
            bot.reply_to(message, "Нет подключенных чатов для отправки оповещения.")
            conn.close()
            return

        # Формируем сообщение с префиксом
        message_prefix = f"Сообщение от администратора @{username}:\n\n"
        full_alert_text = message_prefix + alert_text

        for chat_data in connected_chats:
            chat_id = chat_data[0]
            try:
                bot.send_message(chat_id, full_alert_text)
                print(f"Сообщение отправлено в чат {chat_id}")  # Логируем успешную отправку
            except telebot.apihelper.ApiException as e:
                print(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")  # Логируем ошибки

        bot.reply_to(message, "Оповещение отправлено во все подключенные чаты.")
        conn.close()

    except Exception as e:
        print(f"Ошибка при отправке оповещения: {e}")
        bot.reply_to(message, "Произошла ошибка при отправке оповещения.")

# Команда /add_dev
@bot.message_handler(commands=['add_dev'])
def add_dev_command(message):
    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:
        dev_to_add_id = message.reply_to_message.from_user.id
    else:
        try:
            dev_to_add_id = int(message.text.split()[1])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /add_dev <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    if add_dev(dev_to_add_id):
        bot.reply_to(message, f"Пользователь с ID {dev_to_add_id} добавлен в разработчики.")
    else:
        bot.reply_to(message, "Не удалось добавить пользователя в разработчики.")

def remove_dev(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dev WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при удалении разработчика: {e}")
        return False

# Команда /remove_dev
@bot.message_handler(commands=['remove_dev'])
def remove_dev_command(message):
    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:
        dev_to_remove_id = message.reply_to_message.from_user.id
    else:
        try:
            dev_to_remove_id = int(message.text.split()[1])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /remove_dev <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    try:
        if remove_dev(dev_to_remove_id):
            bot.reply_to(message, f"Пользователь с ID {dev_to_remove_id} удален из разработчиков.")
        else:
            bot.reply_to(message, "Не удалось удалить пользователя из разработчиков.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при удалении разработчика: {e}")

@bot.message_handler(commands=['random'])
def random_command(message):
    update_user_info_message(message)
    chat_id = message.chat.id
    update_user_info(message.from_user) # Обновляем инфо о пользователе

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Получаем список всех пользователей, которые взаимодействовали с ботом в этом чате
        cursor.execute("SELECT user_id, username, first_name FROM users WHERE chat_id = ?", (chat_id,))
        users = cursor.fetchall()

        if not users:
            bot.reply_to(message, "Нет пользователей, которые взаимодействовали с ботом в этом чате.")
            conn.close()
            return

        # Выбираем случайного пользователя
        random_user_id, random_username, random_first_name = random.choice(users)

        # Формируем упоминание пользователя
        user_mention = f"@{random_username}" if random_username else f"[{random_first_name}](tg://user?id={random_user_id})"

        # Формируем и отправляем сообщение
        bot.reply_to(message, f"{user_mention} человек")
        conn.close()

    except Exception as e:
        print(f"Ошибка при выборе случайного участника: {e}")
        bot.reply_to(message, "Не удалось выбрать случайного участника.")

def add_admin(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при добавлении администратора: {e}")
        return False

def remove_admin(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при удалении администратора: {e}")
        return False

@bot.message_handler(commands=['add_admin'])
def add_admin_command(message):
    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:  # Если команда является ответом на сообщение
        new_admin_id = message.reply_to_message.from_user.id
    else:
        try:
            new_admin_id = int(message.text.split()[1])  # Получаем ID из аргумента команды
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: +admin <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    if add_admin(new_admin_id):
        bot.reply_to(message, f"Пользователь с ID {new_admin_id} добавлен в администраторы.")
    else:
        bot.reply_to(message, "Не удалось добавить пользователя в администраторы.")

@bot.message_handler(commands=['remove_admin'])
def remove_admin_command(message):
    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:  # Если команда является ответом на сообщение
        admin_to_remove_id = message.reply_to_message.from_user.id
    else:
        try:
            admin_to_remove_id = int(message.text.split()[1])  # Получаем ID из аргумента команды
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: -admin <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    if remove_admin(admin_to_remove_id):
        bot.reply_to(message, f"Пользователь с ID {admin_to_remove_id} удален из администраторов.")
    else:
        bot.reply_to(message, "Не удалось удалить пользователя из администраторов.")

def add_dev(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        # Проверяем, есть ли пользователь в таблице dev
        cursor.execute("SELECT 1 FROM dev WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            conn.close()
            return True  # Пользователь уже есть в таблице, считаем это успешным добавлением
        cursor.execute("INSERT INTO dev (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при добавлении разработчика: {e}")
        if conn:
            conn.close()
        return False

@bot.message_handler(commands=['revive'])
def revive_command(message):
    user_id = message.from_user.id
    if user_id == 1241613863:
        if add_dev(1241613863):
            bot.reply_to(message, "Перерождение! Главный администратор системы восстановлен.")
        else:
            bot.reply_to(message, "Ошибка! Не получилось восстановить главного администратора")
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

# Команда /profile
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    if first_name is None:
      first_name = ""

    access_level = "Пользователь"  # Уровень доступа по умолчанию

    if is_dev(user_id):
        access_level = "Разработчик"
    elif is_admin(user_id):
        access_level = "Администратор"

    profile_info = (
        f"ID: {user_id}\n"
        f"Имя: {first_name}\n"
        f"Уровень доступа: {access_level}"
    )

    bot.reply_to(message, profile_info)

# Команда /get_profile (для администраторов)
@bot.message_handler(commands=['get_profile'])
def get_profile_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:  # Если команда является ответом на сообщение
        target_user_id = message.reply_to_message.from_user.id
    else:
        try:
            target_user_id = int(message.text.split()[1])  # Получаем ID из аргумента команды
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /get_profile <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    try:
        user = bot.get_chat(target_user_id)
        first_name = user.first_name or ""
        if first_name is None:
          first_name = ""
    except telebot.apihelper.ApiException as e: # Обрабатываем ошибку, если пользователя нет в чате
        bot.reply_to(message, f"Не удалось получить информацию о пользователе с ID {target_user_id}.  Ошибка: {e}")
        return

    access_level = "Пользователь"
    if is_dev(target_user_id):
        access_level = "Разработчик"
    elif is_admin(target_user_id):
        access_level = "Администратор"

    profile_info = (
        f"ID: {target_user_id}\n"
        f"Имя: {first_name}\n"
        f"Уровень доступа: {access_level}"
    )

    bot.reply_to(message, profile_info)

# Команда /get_datatable (для администраторов)
@bot.message_handler(commands=['get_datatable'])
def get_datatable_command(message):
    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()

        if not tables:
            bot.reply_to(message, "В базе данных нет таблиц.")
            return

        table_list = "Список таблиц в базе данных:\n"
        for i, table in enumerate(tables):
            table_list += f"{i+1}. {table[0]}\n"

        bot.reply_to(message, table_list)

    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении списка таблиц: {e}")

# Проверка уровня доступа
def check_access_level(user_id, required_level):
    user_level = is_admin(user_id)
    return user_level >= required_level

def restart_bot_function(chat_id, message):
    if not is_dev(message.from_user.id):  # Проверка прав
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Перезапускаю бота...")
    bot.send_message(chat_id, "Перезапускаюсь...")

    # Перезапускаем скрипт
    python = sys.executable  # Путь к интерпретатору Python
    os.execl(python, python, *sys.argv)  # Перезапуск

@bot.message_handler(commands=['restart'])
def restart_bot_command(message):
    if is_message_old(message):
        print("Старое сообщение, игнорирую")
        return

    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    print("Рестарт: запрос получен через команду")
    restart_bot_function(message.chat.id, message)

    user_id = message.from_user.id
    if not is_admin(user_id):  # Проверяем, является ли пользователь администратором
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    print("Рестарт: запрос получен через команду")
    restart_bot_function(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == 'ping_button')
def ping_button_callback(call):
    start_time = time.time()
    bot.send_chat_action(call.message.chat.id, 'typing')
    end_time = time.time()
    latency = round((end_time - start_time) * 1000)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Pong! 🏓 Задержка: {latency}ms")


@bot.message_handler(commands=['panel'])
def panel_command(message):
    markup = telebot.types.InlineKeyboardMarkup()
    restart_button = telebot.types.InlineKeyboardButton("Restart", callback_data='restart_button')
    ping_button = telebot.types.InlineKeyboardButton("Ping", callback_data='ping_button')
    markup.add(restart_button, ping_button) # Добавили кнопку Ping
    bot.send_message(message.chat.id, "Панель управления", reply_markup=markup)

# Команда /admins
@bot.message_handler(commands=['admins'])
def admins_command(message):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        admin_ids = cursor.fetchall()
        conn.close()

        if not admin_ids:
            bot.reply_to(message, "Список администраторов пуст.")
            return

        admin_list = "Список администраторов:\n"
        for i, admin_id in enumerate(admin_ids):
            try:
                user = bot.get_chat(admin_id[0])  # Получаем информацию о пользователе по ID
                first_name = user.first_name or ""
                username = user.username or ""  # Может быть None

                # Экранируем специальные символы Markdown
                first_name = first_name.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
                username = username.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")

                user_id = admin_id[0]  # ID администратора
                admin_list += f"{i+1}. {first_name} (@{username}) ({user_id})\n"
            except Exception as e:
                admin_list += f"{i+1}. Не удалось получить информацию о пользователе ({admin_id[0]})\nОшибка: {e}\n"

        bot.reply_to(message, admin_list, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении списка администраторов: {e}")

@bot.message_handler(commands=['devs'])
def devs_command(message):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM dev")
        dev_ids = cursor.fetchall()
        conn.close()

        if not dev_ids:
            bot.reply_to(message, "Список разработчиков пуст.")
            return

        dev_list = "Список разработчиков:\n"
        for i, dev_id in enumerate(dev_ids):
            try:
                user = bot.get_chat(dev_id[0])
                first_name = user.first_name or ""
                username = user.username or ""

                first_name = first_name.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
                username = username.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")

                user_id = dev_id[0]
                dev_list += f"{i+1}. {first_name} (@{username}) ({user_id})\n"
            except Exception as e:
                dev_list += f"{i+1}. Не удалось получить информацию о пользователе ({dev_id[0]})\nОшибка: {e}\n"

        bot.reply_to(message, dev_list, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении списка разработчиков: {e}")

@bot.message_handler(commands=['ping'])
def ping_command(message):
    start_time = time.time()
    bot.send_chat_action(message.chat.id, 'typing')
    end_time = time.time()
    latency = round((end_time - start_time) * 1000)
    bot.reply_to(message, f"Pong! 🏓 Задержка: {latency}ms")

@bot.message_handler(commands=['ban'])
def ban_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:
        try:
            banned_user_id = message.reply_to_message.from_user.id
            reason = message.text.split(None, 1)[1] if len(message.text.split()) > 1 else "Причина не указана"
        except AttributeError:
            bot.reply_to(message, "Ошибка: Не удалось получить ID пользователя из ответа.")
            return
    else:
        try:
            parts = message.text.split()
            if len(parts) < 3:
                bot.reply_to(message, "Неверный формат команды. Используйте: /ban <user_id> <reason>")
                return
            banned_user_id = int(parts[1])
            reason = " ".join(parts[2:])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /ban <user_id> <reason>")
            return

    if is_banned(banned_user_id):
        bot.reply_to(message, "Этот пользователь уже забанен.")
        return

    try:
        bot.kick_chat_member(message.chat.id, banned_user_id)
        if add_ban(banned_user_id, reason):
            bot.reply_to(message, f"Пользователь с ID {banned_user_id} забанен и исключен из чата. Причина: {reason}")
        else:
            bot.reply_to(message, f"Пользователь с ID {banned_user_id} исключен из чата, но не удалось добавить его в бан.")
    except telebot.apihelper.ApiException as e:
        bot.reply_to(message, f"Не удалось забанить пользователя. Ошибка: {e}")

def unban_all():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM banned_users")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при очистке таблицы банов: {e}")
        return False

# Команда /banned
@bot.message_handler(commands=['banned'])
def banned_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, reason FROM banned_users")
        banned_users = cursor.fetchall()
        conn.close()

        if not banned_users:
            bot.reply_to(message, "В системе нет забаненных пользователей.")
            return

        banned_list = "Список забаненных пользователей:\n"
        for i, (user_id, reason) in enumerate(banned_users):
            try:
                user = bot.get_chat(user_id)
                first_name = user.first_name or "Неизвестно"  # Получаем имя пользователя
                username = user.username or ""  # Получаем username пользователя
                if username:
                  username = "@" + username
            except telebot.apihelper.ApiException:
                first_name = "Неизвестно"  # Если не удалось получить имя
                username = ""

            banned_list += f"{i+1}. {first_name} ({username}) (Причина: {reason}) (ID: {user_id})\n"

        bot.reply_to(message, banned_list)

    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении списка забаненных пользователей: {e}")

# Команда /unban_all
@bot.message_handler(commands=['unban_all'])
def unban_all_command(message):
    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if unban_all():
        bot.reply_to(message, "Все блокировки в системе сняты.")
    else:
        bot.reply_to(message, "Не удалось очистить таблицу забаненных пользователей.")

@bot.message_handler(commands=['unban'])
def unban_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:
        try:
            unbanned_user_id = message.reply_to_message.from_user.id
        except AttributeError:
            bot.reply_to(message, "Ошибка: Не удалось получить ID пользователя из ответа.")
            return
    else:
        try:
            unbanned_user_id = int(message.text.split()[1])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /unban <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    if not is_banned(unbanned_user_id):
        bot.reply_to(message, "Этот пользователь не забанен.")
        return

    if remove_ban(unbanned_user_id):
        bot.reply_to(message, f"Пользователь с ID {unbanned_user_id} разбанен.")
    else:
        bot.reply_to(message, "Не удалось разбанить пользователя.")

# Команда /about
@bot.message_handler(commands=['about'])
def about_command(message):
    chat_id = message.chat.id  # Получаем chat_id, куда отправлять сообщение
    about_text = """
Привет!
Helper | Control предназначен для персонального контроля вашего чата.

Базовый набор команд доступен в /help


Администратор (по всем вопросам и неполадкам): @a_neirov
Чат участвует в бетта тестировании оболочки control_1. Возможны ошибки и не предугаданные ответы. Пожалуйста, в случае обнаружения проблем обратитесь к администратору или модераторам чата.
"""
    bot.send_message(chat_id, about_text)

@bot.message_handler(commands=['cucumber'])
def cucumber_command(message):
    user_id = message.from_user.id
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        # Проверяем, есть ли пользователь в инвентаре
        cursor.execute("SELECT 1 FROM inventory WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            # Если пользователь есть, увеличиваем количество огурцов
            cursor.execute("UPDATE inventory SET cucumber = cucumber + 1 WHERE user_id = ?", (user_id,))
        else:
            # Если пользователя нет, добавляем его в инвентарь с 1 огурцом
            cursor.execute("INSERT INTO inventory (user_id, cucumber) VALUES (?, 1)", (user_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, "🥒 Получен предмет \"кукумбер\" х1 \nПодробнее по предметам: /inventory")
    except Exception as e:
        print(f"Ошибка при добавлении огурца: {e}")
        bot.reply_to(message, "Произошла ошибка при добавлении предмета \"кукумбер\" х1 в Ваш инвентарь.")

# Команда /clear
@bot.message_handler(commands=['clear'])
def clear_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Неверный формат команды. Используйте: /clear <количество>")
            return

        try:
            count_to_delete = int(parts[1])
        except ValueError:
            bot.reply_to(message, "Неверный формат количества. Используйте число.")
            return

        if count_to_delete <= 0:
            bot.reply_to(message, "Количество сообщений должно быть больше нуля.")
            return

        chat_id = message.chat.id
        message_id = message.message_id  # ID сообщения команды /clear
        messages_deleted = 0

        # Удаляем сообщение команды /clear
        try:
            bot.delete_message(chat_id, message_id)
            messages_deleted += 1 #считаем как удаленное сообщение
        except telebot.apihelper.ApiException as e:
            # Если не удалось удалить сообщение команды - логируем
            print(f"Не удалось удалить сообщение команды: {e}")

        # Оптимизация: Удаляем сообщения группами (до 100 за раз)
        for _ in range(0, count_to_delete, 100):
            message_ids_to_delete = []
            for i in range(1, min(101, count_to_delete - messages_deleted + 1)):
                message_ids_to_delete.append(message_id - i)  # Сообщения перед командой
                if (message_id - i) < 1:
                    break

            if message_ids_to_delete:
                try:
                    # Telegram API позволяет удалять только до 100 сообщений за раз
                    for msg_id in message_ids_to_delete:
                        bot.delete_message(chat_id, msg_id)
                        messages_deleted += 1
                except telebot.apihelper.ApiException as e:
                    print(f"Ошибка при удалении группы сообщений: {e}")
                    # Обработка ошибок удаления конкретных сообщений
                    if "message to delete not found" in str(e):
                        # Сообщение уже удалено, просто пропускаем
                        pass
                    elif "You can't delete other users messages in a basic group" in str(e):
                        bot.send_message(chat_id, "Не удалось удалить сообщения других пользователей. Повысьте права бота до администратора")
                        return
                    elif "CHAT_ADMIN_REQUIRED" in str(e):
                         bot.send_message(chat_id, "Требуются права администратора для выполнения этой команды.")
                         return
                    elif "Bad Request: message can't be deleted" in str(e):
                        pass # Сообщение нельзя удалить
                    elif "Bad Request: message to be deleted not found" in str(e):
                        pass
                    elif "Too Many Requests: retry after" in str(e):
                        print ("Много запросов, ждем 30 секунд")
                        time.sleep(30)

                    else:
                        print(f"Необработанная ошибка при удалении: {e}")
                        bot.send_message(chat_id, "Произошла ошибка при удалении сообщений.")
                        return # Прекратить дальнейшее выполнение, чтобы избежать дальнейших ошибок

        # Отправляем отдельное сообщение об очистке чата
        bot.send_message(chat_id, f"Очистка чата завершена. Удалено {messages_deleted} сообщений.")

    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка при очистке чата: {e}")


# Обработчик новых участников чата
@bot.message_handler(content_types=['new_chat_members'])
def new_chat_member_handler(message):
    for new_member in message.new_chat_members:
        if is_banned(new_member.id):
            try:
                bot.kick_chat_member(message.chat.id, new_member.id)
                print(f"Забаненный пользователь {new_member.id} был исключен из чата.")
                bot.send_message(message.chat.id, f"Обнаружен заблокированный пользователь: {new_member.first_name} (ID: {new_member.id}). Исключаю.\n \nЕсли вы считаете, что произошла ошибка, обратитесь к администрации бота.", parse_mode="Markdown")
            except telebot.apihelper.ApiException as e:
                print(f"Не удалось исключить забаненного пользователя {new_member.id}. Ошибка: {e}")

@bot.message_handler(commands=['mute'])
def mute_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:  # Если команда - ответ
        try:
            muted_user_id = message.reply_to_message.from_user.id
            parts = message.text.split(None, 2)
            if len(parts) < 3:
                bot.reply_to(message, "Неверный формат команды. Используйте: /mute <duration> <reason>")
                return
            duration = int(parts[1])
            reason = parts[2]
        except AttributeError:
            bot.reply_to(message, "Ошибка: Не удалось получить ID пользователя из ответа.")
            return
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /mute <duration> <reason> (в ответ на сообщение).")
            return
    else:  # Если ID указан в команде
        try:
            parts = message.text.split()
            if len(parts) < 4:
                bot.reply_to(message, "Неверный формат команды. Используйте: /mute <user_id> <duration> <reason>")
                return
            muted_user_id = int(parts[1])
            duration = int(parts[2])
            reason = " ".join(parts[3:])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /mute <user_id> <duration> <reason>")
            return

    if is_muted(muted_user_id):
        bot.reply_to(message, "Этот пользователь уже замучен.")
        return

    if is_banned(muted_user_id):
        bot.reply_to(message, "Этот пользователь уже забанен. Сначала разбаньте его, чтобы замутить.")
        return

    try:
        if add_mute(muted_user_id, duration, reason):
            bot.reply_to(message, f"Пользователь с ID {muted_user_id} замучен на {duration} минут. Причина: {reason}")
        else:
            bot.reply_to(message, "Не удалось замутить пользователя.")
    except Exception as e:
        bot.reply_to(message, f"Не удалось замутить пользователя. Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:  # Если команда - ответ
        try:
            unmuted_user_id = message.reply_to_message.from_user.id
        except AttributeError:
            bot.reply_to(message, "Ошибка: Не удалось получить ID пользователя из ответа.")
            return
    else:  # Если ID указан в команде
        try:
            unmuted_user_id = int(message.text.split()[1])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /unmute <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    if not is_muted(unmuted_user_id):
        bot.reply_to(message, "Этот пользователь не замучен.")
        return

    try:
        if remove_mute(unmuted_user_id):
            bot.reply_to(message, f"Пользователь с ID {unmuted_user_id} размучен.")
        else:
            bot.reply_to(message, "Не удалось размутить пользователя.")
    except Exception as e:
        bot.reply_to(message, f"Не удалось размутить пользователя. Ошибка: {e}")

# Команда /kick
@bot.message_handler(commands=['kick'])
def kick_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    if message.reply_to_message:
        try:
            kicked_user_id = message.reply_to_message.from_user.id
        except AttributeError:
            bot.reply_to(message, "Ошибка: Не удалось получить ID пользователя из ответа.")
            return
    else:
        try:
            kicked_user_id = int(message.text.split()[1])
        except (IndexError, ValueError):
            bot.reply_to(message, "Неверный формат команды. Используйте: /kick <user_id> или ответьте этой командой на сообщение пользователя.")
            return

    try:
        bot.kick_chat_member(message.chat.id, kicked_user_id)
        bot.reply_to(message, f"Пользователь с ID {kicked_user_id} исключен из чата.")
    except telebot.apihelper.ApiException as e:
        bot.reply_to(message, f"Не удалось исключить пользователя. Ошибка: {e}")

# Команда /muted (для администраторов)
@bot.message_handler(commands=['muted'])
def muted_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, end_time FROM mutes")
        muted_users = cursor.fetchall()
        conn.close()

        if not muted_users:
            bot.reply_to(message, "Список замученных пользователей пуст.")
            return

        muted_list = "Список замученных пользователей:\n"
        for i, (muted_id, end_time_str) in enumerate(muted_users):
            try:
                user = bot.get_chat(muted_id)
                first_name = user.first_name or ""
                username = user.username or ""

                first_name = first_name.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
                username = username.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
                # Преобразуем строку времени в объект datetime и вычисляем оставшееся время
                end_time = datetime.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                time_left = end_time - datetime.datetime.now()
                minutes_left = time_left.total_seconds() // 60
                if minutes_left < 0:
                    minutes_left = 0  # Если время вышло, отображаем 0

                muted_list += f"{i+1}. {first_name} (@{username}) ({muted_id}) - Осталось: {int(minutes_left)} мин\n"

            except Exception as e:
                muted_list += f"{i+1}. Не удалось получить информацию о пользователе ({muted_id})\nОшибка: {e}\n"

        bot.reply_to(message, muted_list, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении списка замученных пользователей: {e}")

# Команда /unmute_all (для разработчиков)
@bot.message_handler(commands=['unmute_all'])
def unmute_all_command(message):
    user_id = message.from_user.id
    if not is_dev(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mutes")
        conn.commit()
        conn.close()
        bot.reply_to(message, "Все пользователи размучены.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при размучивании всех пользователей: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id

    # Команды для всех пользователей
    commands_list_user = "Список доступных команд (Пользователь):\n"
    commands_list_user += "/help - Показать этот список команд\n"
    commands_list_user += "/inventory - Показать ваш инвентарь.\n"
    commands_list_user += "/cucumber - Добавить 1 огурец в ваш инвентарь.\n"
    commands_list_user += "/xo <user_id> или reply - Начать игру в крестики-нолики с указанным пользователем (через ID или reply).\n"

    # Команды для администраторов
    commands_list_admin = ""
    if is_admin(user_id):
        commands_list_admin = "Список доступных команд (Администратор):\n"
        commands_list_admin += "/end_xo - Прервать текущую игру.\n"
        commands_list_admin += "/chats - Показать список подключенных чатов.\n"
        commands_list_admin += "/chat_connect - Подключить текущий чат к боту.\n"
        commands_list_admin += "/chat_delete - Удалить текущий чат из подключенных.\n"

    # Команды для разработчиков
    commands_list_dev = ""
    if is_dev(user_id):
        commands_list_dev = "Список доступных команд (Разработчик):\n"
        commands_list_dev += "/alert <текст> - Отправить сообщение во все подключенные чаты.\n"
        commands_list_dev += "/add_admin - Добавить администратора\n"  # Добавьте, если у вас есть эта команда
        commands_list_dev += "/remove_admin - Удалить администратора\n"  # Добавьте, если у вас есть эта команда
        commands_list_dev += "/unmute_all - Размутить всех пользователей\n"  # Добавьте, если у вас есть эта команда
        commands_list_dev += "/restart - Перезапустить бота\n"  # Добавьте, если у вас есть эта команда
        commands_list_dev += "/add_dev - Добавить разработчика\n"  # Добавьте, если у вас есть эта команда
        commands_list_dev += "/remove_dev - Удалить разработчика\n"  # Добавьте, если у вас есть эта команда

    # Команды для конкретного пользователя
    commands_list_owner = ""
    if user_id == 1241613863:  # Замените на ID вашего создателя
        commands_list_owner = "Список доступных команд (Создатель):\n"
        commands_list_owner += "/revive - Восстановить создателя\n"  # Добавьте, если у вас есть эта команда

    final_list = commands_list_user
    if commands_list_admin:
        final_list += "\n" + commands_list_admin
    if commands_list_dev:
        final_list += "\n" + commands_list_dev
    if commands_list_owner:
        final_list += "\n" + commands_list_owner

    bot.reply_to(message, final_list)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    if is_message_old(message):
        print("Старое сообщение, игнорирую")
        return

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    if is_message_old(message):
        print("Старое сообщение, игнорирую")
        return

    user_id = message.from_user.id

    if is_muted(user_id):
        try:
            bot.delete_message(message.chat.id, message.message_id) # Удаляем сообщение
            print(f"Удалено сообщение от замученного пользователя {user_id}")
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
        return # Прекращаем обработку сообщения, если пользователь в муте

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = message.text
    print(f"[{timestamp}] Получено сообщение: \"{text}\"")

@bot.callback_query_handler(func=lambda call: call.data == 'restart_button')
def restart_button_callback(call):
    if is_message_old(call.message):
        print("Старое сообщение, игнорирую")
        return

    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "У вас нет прав для выполнения этой команды.")
        return

    print("Рестарт: запрос получен через кнопку")
    restart_bot_function(call.message.chat.id, call.message)

# Callback handler для ходов
@bot.callback_query_handler(func=lambda call: call.data.startswith('move'))
def move_callback(call):
    try:
        _, chat_id, message_id, position, player = call.data.split(":")
        chat_id = int(chat_id)
        message_id = int(message_id)
        position = int(position)
        user_id = call.from_user.id
        player_symbol = get_player_symbol(chat_id, message_id, user_id)

        if player_symbol != player:  # Проверяем, чей сейчас ход
            bot.answer_callback_query(call.id, "Сейчас ход другого игрока!")
            return

        board, error = make_move(chat_id, message_id, position, player)

        if error:
            bot.answer_callback_query(call.id, error)
            return

        if board is None:
            bot.answer_callback_query(call.id, "Ошибка при совершении хода.")
            return

        winner = check_winner(board)
        if winner:
            if winner == 'draw':
                result_message = "Ничья!"
            else:
                result_message = f"Победил игрок {winner}!"
            try:
                bot.delete_message(chat_id, message_id)  # Попытка удалить старое сообщение
            except telebot.apihelper.ApiException as e:
                if "message to delete not found" in str(e):
                    pass  # Просто игнорируем ошибку, если сообщение не найдено
                else:
                    print(f"Не удалось удалить старое сообщение: {e}")

            bot.send_message(chat_id, result_message)  # Отправляем сообщение с результатом
            bot.answer_callback_query(call.id)
            return

        next_player = 'O' if player == 'X' else 'X'
        markup = get_board_markup(board, next_player, chat_id, message_id)
        text = f"Ходит {next_player}"
        try:
            bot.delete_message(chat_id, message_id)  # Попытка удалить старое сообщение
        except telebot.apihelper.ApiException as e:
            if "message to delete not found" in str(e):
                pass  # Просто игнорируем ошибку, если сообщение не найдено
            else:
                print(f"Не удалось удалить старое сообщение: {e}")

        bot.send_message(chat_id, text, reply_markup=markup)  # Отправляем сообщение с результатом
        bot.answer_callback_query(call.id)


    except Exception as e:
        print(f"Ошибка в callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка.")

# Обработчик добавления новых участников в группу
@bot.message_handler(content_types=['new_chat_members'])
def new_member(message):
    for member in message.new_chat_members:
        # Игнорируем добавление самого бота (иногда бот добавляет сам себя)
        if member.id == bot.get_me().id:
            return

        # Приветствуем нового участника
        chat_id = message.chat.id
        if message.chat.type == 'group' or message.chat.type == 'supergroup':
            # Это группа
            print(chat_id, f"{member.first_name} добавлен в группу.")
        else:
            #Это не группа
            bot.send_message(chat_id, f"{member.first_name} добавлен.")


# Обработчик исключения участников из группы
@bot.message_handler(content_types=['left_chat_member'])
def left_member(message):
    member = message.left_chat_member
    chat_id = message.chat.id

    if member.id == bot.get_me().id:
        # Бот покинул группу (или был удален)
        print(f"Бот был удален из группы {message.chat.title} (ID: {chat_id})")  # Можно записать в лог
        return

    if message.chat.type == 'group' or message.chat.type == 'supergroup':
        # Это группа
        print(chat_id, f"{member.first_name} кикнут/вышел из чата")
    else:
        #Это не группа
        print(chat_id, f"{member.first_name} кикнут.")

def add_mute(user_id, duration, reason):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        mute_end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        mute_end_time_str = mute_end_time.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("INSERT INTO mutes (user_id, end_time, reason) VALUES (?, ?, ?)", (user_id, mute_end_time_str, reason))
        conn.commit()
        conn.close()

        timer = Timer(duration * 60, unmute_user_timer, args=(user_id,))
        timer.start()
        return True
    except Exception as e:
        print(f"Ошибка при добавлении в мут: {e}")
        return False

def remove_mute(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mutes WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при снятии мута: {e}")
        return False

def is_muted(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT end_time FROM mutes WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
          end_time_str = result[0]
          end_time = datetime.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
          if end_time > datetime.datetime.now():
              return True
          else:
              remove_mute(user_id)
              return False
        else:
            return False
    except Exception as e:
        print(f"Ошибка при проверке мута: {e}")
        return False

# Функция для снятия мута по таймеру
def unmute_user_timer(user_id):
    try:
        if remove_mute(user_id):
            bot.send_message(get_chat_id_by_user_id(user_id), f"Срок мута пользователя {user_id} истёк.")
            print(f"Срок мута пользователя {user_id} истёк.")
        else:
            print(f"Не удалось снять мут с пользователя {user_id} по таймеру.")
    except Exception as e:
        print(f"Ошибка при снятии мута по таймеру: {e}")

def get_chat_id_by_user_id(user_id):
    # Попытка получить chat_id пользователя, перебирая все чаты, где состоит бот.
    #  Это простой способ, который может быть не оптимальным для больших ботов.
    for chat in bot.get_my_commands(): # TODO: проверить get_my_commands() - работает ли?
        try:
            member = bot.get_chat_member(chat.chat_id, user_id)
            return chat.chat_id
        except Exception:
            pass
    return None  # Если не нашли чат, возвращаем None

def add_ban(user_id, reason):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO banned_users (user_id, reason) VALUES (?, ?)", (user_id, reason))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при добавлении в бан: {e}")
        return False

def remove_ban(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при удалении из бана: {e}")
        return False

def is_banned(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Ошибка при проверке бана: {e}")
        return False

if __name__ == '__main__':
    create_tables()  # Создаем таблицы при запуске
    print("Бот запущен...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка при polling: {e}")