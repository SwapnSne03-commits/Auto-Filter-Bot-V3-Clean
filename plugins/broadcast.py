import asyncio
import time
import datetime
from logging_helper import LOGGER

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from database.users_chats_db import db
from info import ADMINS
from utils import (
    users_broadcast,
    groups_broadcast,
    clear_junk,
    junk_group,
    temp,
    get_readable_time
)


# =====================================================
# ⚙️ GLOBAL SAFE SETTINGS (Koyeb Free Optimized)
# =====================================================

MIN_BATCH = 15
MAX_BATCH = 50
RETRY_LIMIT = 2
DELAY = 0.01

lock = asyncio.Lock()


# =====================================================
# 🔥 AUTO SPEED CONTROL
# =====================================================

def auto_batch_size(total):
    if total < 2000:
        return 45
    elif total < 8000:
        return 30
    else:
        return 25


# =====================================================
# 🔥 PROGRESS BAR
# =====================================================

def progress_bar(done, total):
    percent = int((done / total) * 100) if total else 0
    filled = percent // 5
    return f"[{'█'*filled}{'░'*(20-filled)}] {percent}%"


# =====================================================
# 🔥 SAFE SEND WITH RETRY
# =====================================================

async def safe_user_send(uid, msg, is_pin):
    for _ in range(RETRY_LIMIT):
        try:
            _, res = await users_broadcast(uid, msg, is_pin)
            return res

        except FloodWait as e:
            await asyncio.sleep(e.value)

        except Exception:
            await asyncio.sleep(1)

    return "Error"


async def safe_group_send(cid, msg, is_pin):
    for _ in range(RETRY_LIMIT):
        try:
            return await groups_broadcast(cid, msg, is_pin)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            await asyncio.sleep(1)
    return "Error"


# =====================================================
# 🔥 CANCEL BUTTON
# =====================================================

@Client.on_callback_query(filters.regex(r'^broadcast_cancel'))
async def cancel_broadcast(_, query):
    target = query.data.split("#")[-1]

    if target == "users":
        temp.B_USERS_CANCEL = True
    else:
        temp.B_GROUPS_CANCEL = True

    await query.message.edit("🛑 Broadcast cancelling...")


# =====================================================
# 🔥 USER BROADCAST
# =====================================================

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_users(bot, message):

    if lock.locked():
        return await message.reply("⚠️ Another broadcast running...")

    ask = await message.reply(
        "📌 Pin message?",
        reply_markup=ReplyKeyboardMarkup(
            [["Yes", "No"]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    try:
        ans = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=60)
    except asyncio.TimeoutError:
        return await message.reply("❌ Timeout")

    await ask.delete()

    is_pin = ans.text == "Yes"
    b_msg = message.reply_to_message

    cursor = await db.get_all_users()
    total = await db.total_users_count()

    batch_size = auto_batch_size(total)

    status = await message.reply_text("🚀 Starting broadcast...")

    success = blocked = deleted = failed = done = 0
    start = time.time()

    async with lock:

        tasks = []

        async for user in cursor:

            if temp.B_USERS_CANCEL:
                temp.B_USERS_CANCEL = False
                break

            tasks.append(safe_user_send(int(user["id"]), b_msg, is_pin))

            if len(tasks) >= batch_size:

                results = await asyncio.gather(*tasks, return_exceptions=True)
                tasks.clear()

                for r in results:
                    if r == "Success": success += 1
                    elif r == "Blocked": blocked += 1
                    elif r == "Deleted": deleted += 1
                    else: failed += 1

                done += len(results)

                # dynamic adjust
                if failed > 5:
                    batch_size = max(MIN_BATCH, batch_size - 3)
                else:
                    batch_size = min(MAX_BATCH, batch_size + 1)

                await asyncio.sleep(DELAY)

                bar = progress_bar(done, total)

                try:
                    await status.edit(
                        f"📣 Broadcasting...\n\n"
                        f"{bar}\n\n"
                        f"👥 {done}/{total}\n"
                        f"✅ {success} | ❌ {failed}",
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel#users")]]
                        )
                    )
                except:
                    pass

        if tasks:
            await asyncio.gather(*tasks)

    elapsed = get_readable_time(time.time() - start)

    await status.edit(
        f"✅ Broadcast Completed\n\n"
        f"🕒 {elapsed}\n"
        f"📬 Success {success}\n"
        f"⛔ Blocked {blocked}\n"
        f"🗑 Deleted {deleted}\n"
        f"❌ Failed {failed}"
    )


# =====================================================
# 🔥 GROUP BROADCAST
# =====================================================

@Client.on_message(filters.command("grp_broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_groups(bot, message):

    if lock.locked():
        return await message.reply("⚠️ Another broadcast running...")

    b_msg = message.reply_to_message

    cursor = await db.get_all_chats()
    total = await db.total_chat_count()

    batch_size = auto_batch_size(total)

    status = await message.reply_text("🚀 Broadcasting to groups...")

    success = failed = done = 0
    start = time.time()

    async with lock:

        tasks = []
        edit_counter = 0

        async for chat in cursor:

            if temp.B_GROUPS_CANCEL:
                temp.B_GROUPS_CANCEL = False
                break

            tasks.append(safe_group_send(int(chat["id"]), b_msg, False))

            if len(tasks) >= batch_size:

                results = await asyncio.gather(*tasks, return_exceptions=True)
                tasks.clear()

                edit_counter += 1

                for r in results:
                    if r == "Success":
                        success += 1
                    else:
                        failed += 1

                done += len(results)

                await asyncio.sleep(DELAY)

                if edit_counter % 3 == 0:
                    bar = progress_bar(done, total)

                    await status.edit(f"📣 Group Broadcast\n\n{bar}\n{done}/{total}")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if r == "Success":
                    success += 1
                else:
                    failed += 1

            done += len(results)
    elapsed = get_readable_time(time.time() - start)

    await status.edit(
        f"✅ Group Broadcast Done\n\n"
        f"🕒 {elapsed}\n"
        f"Success {success}\n"
        f"Failed {failed}"
    )


# =====================================================
# 🔥 JUNK USER CLEAN
# =====================================================

@Client.on_message(filters.command("clear_junk") & filters.user(ADMINS))
async def remove_junk_users(bot, message):

    if lock.locked():
        return await message.reply("⚠️ Broadcast running...")

    users = await db.get_all_users()
    total = await db.total_users_count()

    sts = await message.reply("Cleaning users...")

    blocked = deleted = failed = done = 0
    start = time.time()

    async with lock:

        async for user in users:
            pti, sh = await clear_junk(int(user["id"]), message)

            if not pti:
                if sh == "Blocked": blocked += 1
                elif sh == "Deleted": deleted += 1
                else: failed += 1

            done += 1

            if done % 50 == 0:
                await sts.edit(f"{done}/{total}")

    elapsed = get_readable_time(time.time() - start)

    await sts.edit(
        f"✅ Clean Done\n\n"
        f"Blocked {blocked}\nDeleted {deleted}\nFailed {failed}\n⏱ {elapsed}"
    )


# =====================================================
# 🔥 JUNK GROUP CLEAN
# =====================================================

@Client.on_message(filters.command(["junk_group", "clear_junk_group"]) & filters.user(ADMINS))
async def remove_junk_groups(bot, message):

    if lock.locked():
        return await message.reply("⚠️ Broadcast running...")

    groups = await db.get_all_chats()
    total = await db.total_chat_count()

    sts = await message.reply("Cleaning groups...")

    deleted = done = 0
    start = time.time()

    async with lock:

        async for group in groups:

            pti, sh, _ = await junk_group(int(group["id"]), message)

            if not pti and sh == "deleted":
                deleted += 1
                try:
                    await bot.leave_chat(int(group["id"]))
                except:
                    pass

            done += 1

            if done % 50 == 0:
                await sts.edit(f"{done}/{total}")

    elapsed = get_readable_time(time.time() - start)

    await sts.edit(f"✅ Groups Cleaned {deleted}\n⏱ {elapsed}")
