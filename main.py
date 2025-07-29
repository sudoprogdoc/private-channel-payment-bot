import logging
from os import getenv
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.callback_data import CallbackData

load_dotenv()
API_TOKEN = getenv("BOT_TOKEN")
ADMIN_CHAT_ID = getenv("CHAT_ID")
channel_id = getenv("CHANNEL_ID")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
messages_data = [
    {
        "text": "1st message"
    },
    {
        "text": "2nd message",
    },
    {
        "text": "3rd message",
        "photo": "https://example.com/img.png"
    },
    {
        "text": "4th message",
        "photo": "https://example.com/img.png"
    },
    {
        "text": "5th message",
        "photo": "https://example.com/img.png"
    },
    {
        "text": "Message about payment",

    }
]
funfacts = [
    "FF 1",
    "FF 2",
    "FF 3",
    "FF 4",
    "FF 5",
    "FF 6"
]


async def send_funfact_message(chat_id, count):
    button = InlineKeyboardButton(text="Случайный интересный факт", callback_data=f"funfact_{count}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    if count > 6:
        await bot.send_message(
            chat_id,
            text="Last FF text" + "\n\n" + messages_data[-1]["text"],
            parse_mode="HTML",
        )
        return
    else: 
        await bot.send_message(
            chat_id,
            text=funfacts[count -1]+ "\n\n" + messages_data[-1]["text"],
            parse_mode="HTML",
            reply_markup=keyboard
        )


@dp.callback_query(lambda c: c.data.startswith('funfact_'))
async def handle_funfact_callback(callback_query: types.CallbackQuery):
    await bot.edit_message_reply_markup(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )
    data = callback_query.data
    count_str = data.split('_')[1]
    count = int(count_str)

    next_count = count + 1
    await send_funfact_message(callback_query.message.chat.id, next_count)
    await callback_query.answer()
    

@dp.message(Command(commands=["start"]))
async def start_handler(message: types.Message):
    await send_message_sequence(message.chat.id, 0)


async def send_message_sequence(chat_id: int, index: int):
    
    if index >= len(messages_data):
        return

    data = messages_data[index]
    if index < len(messages_data) - 1:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Далее", callback_data=f"next_{index + 1}")
                ]
            ]
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Случайный интересный факт", callback_data="funfact_0"),
                ]
            ]
        )

    if "photo" in data:
        await bot.send_photo(
            chat_id,
            photo=data["photo"],
            caption=data["text"],
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await bot.send_message(
            chat_id,
            text=data["text"],
            parse_mode="HTML",
            reply_markup=keyboard
        )

@dp.callback_query(lambda c: c.data and c.data.startswith("next_"))
async def handle_next(callback: types.CallbackQuery):
    await bot.edit_message_reply_markup(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )
    next_index = int(callback.data.split("_")[1])
    
    # Удаляем сообщение с кнопкой (чтобы не засорять чат)
    #await callback.message.delete()
    
    await send_message_sequence(callback.message.chat.id, next_index)
    
    await callback.answer()


pending_payments = {}

class PaymentCallback(CallbackData, prefix="payment"):
    action: str
    msg_id: int

@dp.message(F.photo)
async def handle_payment_screenshot(message: Message):
    user_id = message.from_user.id
    caption = f"Платеж от пользователя: {message.from_user.full_name} (id: {user_id})"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=PaymentCallback(action="approve", msg_id=0).pack()),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=PaymentCallback(action="reject", msg_id=0).pack()),
        ]
    ])
    
    sent = await bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=message.photo[-1].file_id,
        caption=caption,
        reply_markup=keyboard
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=PaymentCallback(action="approve", msg_id=sent.message_id).pack()
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=PaymentCallback(action="reject", msg_id=sent.message_id).pack()
            ),
        ]
    ])
    
    await bot.edit_message_reply_markup(
        chat_id=ADMIN_CHAT_ID,
        message_id=sent.message_id,
        reply_markup=keyboard
    )
    
    pending_payments[sent.message_id] = user_id
    
    await message.answer("Спасибо! Ваш платеж отправлен на проверку.")

@dp.callback_query(PaymentCallback.filter())
async def process_payment_callback(callback: CallbackQuery, callback_data: PaymentCallback):
    
    msg_id = callback_data.msg_id
    action = callback_data.action
    
    if msg_id not in pending_payments:
        await callback.answer("Этот платеж уже обработан или не найден.", show_alert=True)
        return
    
    user_id = pending_payments.pop(msg_id)
    
    if action == "approve":
        try:
            invite = await bot.create_chat_invite_link(chat_id=channel_id, member_limit=1)
            await bot.send_message(user_id, f"Ваш платеж подтверждён! Вот ссылка на канал: {invite.invite_link[8:]}")
            await callback.message.edit_reply_markup()
            await callback.answer("Платеж подтверждён и пользователь уведомлён.")
        except Exception as e:
            await callback.answer(f"Ошибка при уведомлении пользователя: {e}", show_alert=True)
    elif action == "reject":
        try:
            await bot.send_message(user_id, "Ваш платеж не подтверждён. Пожалуйста, свяжитесь с поддержкой.")
            await callback.message.edit_reply_markup()
            await callback.answer("Платеж отклонён и пользователь уведомлён.")
        except Exception as e:
            await callback.answer(f"Ошибка при уведомлении пользователя: {e}", show_alert=True)

@dp.message()
async def handle_text_message(message: types.Message):
    await message.answer("Я не работаю с таким форматом сообщений, используйте другой способ")

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot, skip_updates=True))