import asyncio
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===== STATES =====
class Report(StatesGroup):
    username = State()
    amount = State()
    proof = State()

# ===== KEYBOARDS =====
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚨 Report Scammer")],
        [KeyboardButton(text="📊 My Reports"), KeyboardButton(text="👤 My Profile")],
    ],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Cancel")]],
    resize_keyboard=True
)

# ===== DATABASE =====
reports = []
report_id = 1

# ===== START =====
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"🚨 Scammer Report Bot\n\n"
        f"👤 {message.from_user.full_name}\n"
        f"🆔 {message.from_user.id}\n\n"
        f"👇 Use buttons:",
        reply_markup=main_kb
    )

# ===== START REPORT =====
@dp.message(F.text == "🚨 Report Scammer")
async def report_start(message: Message, state: FSMContext):
    await message.answer("📌 Send scammer username (@username)", reply_markup=cancel_kb)
    await state.set_state(Report.username)

# ===== USERNAME =====
@dp.message(Report.username)
async def get_username(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        return await message.answer("❌ Cancelled", reply_markup=main_kb)

    if not re.match(r"^@[a-zA-Z][a-zA-Z0-9_]{4,31}$", message.text):
        return await message.answer("❌ Invalid username")

    await state.update_data(username=message.text)
    await message.answer("💰 Enter amount:", reply_markup=cancel_kb)
    await state.set_state(Report.amount)

# ===== AMOUNT =====
@dp.message(Report.amount)
async def get_amount(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        return await message.answer("❌ Cancelled", reply_markup=main_kb)

    if not message.text.isdigit():
        return await message.answer("❌ Enter valid amount")

    await state.update_data(amount=message.text)
    await message.answer("📸 Send screenshot proof:", reply_markup=cancel_kb)
    await state.set_state(Report.proof)

# ===== PROOF =====
@dp.message(Report.proof, F.photo)
async def get_proof(message: Message, state: FSMContext):
    global report_id

    data = await state.get_data()
    photo_id = message.photo[-1].file_id

    report = {
        "id": report_id,
        "user": message.from_user.id,
        "username": data["username"],
        "amount": data["amount"],
        "proof": photo_id,
        "status": "pending",
        "confirmed": False
    }

    admin_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"✅ Approve {report_id}")],
            [KeyboardButton(text=f"❌ Reject {report_id}")]
        ],
        resize_keyboard=True
    )

    await bot.send_photo(
        ADMIN_ID,
        photo=photo_id,
        caption=
        f"🚨 NEW REPORT\n\n"
        f"ID: #{report_id}\n"
        f"User: {message.from_user.id}\n"
        f"Scammer: {data['username']}\n"
        f"Amount: {data['amount']}",
        reply_markup=admin_kb
    )

    report_id += 1
    await state.clear()

# ===== PROOF ERROR =====
@dp.message(Report.proof)
async def proof_error(message: Message):
    await message.answer("❌ Send valid screenshot (image only)")

# ===== ADMIN ACTIONS =====
@dp.message()
async def admin_actions(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text

    if "Approve" in text:
        rid = int(text.split()[-1])
        for r in reports:
            if r["id"] == rid:
                r["status"] = "approved"

                await bot.send_message(r["user"], f"✅ Report #{rid} approved")

                # CHANNEL POST
                post_kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📌 View", callback_data=f"info_{rid}")]
                    ]
                )

                await bot.send_photo(
                    CHANNEL_ID,
                    photo=r["proof"],
                    caption=
                    f"🚨 SCAMMER ALERT\n\n"
                    f"👤 {r['username']}\n"
                    f"💰 {r['amount']}\n"
                    f"📌 ID: #{rid}",
                    reply_markup=post_kb
                )

        

    elif "Reject" in text:
        rid = int(text.split()[-1])
        for r in reports:
            if r["id"] == rid:
                r["status"] = "rejected"
                await bot.send_message(r["user"], f"❌ Report #{rid} rejected")

# ===== CONFIRM =====
@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_handler(call: CallbackQuery):
    rid = int(call.data.split("_")[1])

    for r in reports:
        if r["id"] == rid:
            r["confirmed"] = True

            await call.message.edit_text(f"✅ You responded to report #{rid}")

            await bot.send_message(
                ADMIN_ID,
                f"📌 Report #{rid} confirmed by accused user"
            )

# ===== MY REPORTS =====
@dp.message(F.text == "📊 My Reports")
async def my_reports(message: Message):
    user_reports = [r for r in reports if r["user"] == message.from_user.id]

    if not user_reports:
        return await message.answer("❌ No reports")

    text = "📊 Your Reports:\n\n"
    for r in user_reports:
        text += f"#{r['id']} | {r['username']} | {r['amount']} | {r['status']}\n"

    await message.answer(text)

# ===== PROFILE =====
@dp.message(F.text == "👤 My Profile")
async def profile(message: Message):
    await message.answer(
        f"👤 Profile\n\nName: {message.from_user.full_name}\nID: {message.from_user.id}"
    )

# ===== RUN =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
