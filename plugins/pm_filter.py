import asyncio
import re
import ast
import math
import random
import pytz
from datetime import datetime, timedelta, date, time
from database.users_chats_db import db
from database.refer import referdb
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from info import *
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, WebAppInfo
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import *
from fuzzywuzzy import process
from database.users_chats_db import db
from database.ia_filterdb import Media, Media2, get_file_details, get_search_results, get_bad_files
from logging_helper import LOGGER
from urllib.parse import quote_plus
from Lucia.util.file_properties import get_name, get_hash, get_media_file_size
from database.topdb import silentdb
import requests
import string
import tracemalloc

tracemalloc.start()

TIMEZONE = "Asia/Kolkata"
BUTTON = {}
BUTTONS = {}
FRESH = {}
SPELL_CHECK = {}
SPELL_CACHE = {}
POSTER_CACHE = {}         # for advantage_spell_chok (movies list)
CACHE_LIMIT = 200

lock = asyncio.Lock()

def is_meaningful_query(search: str) -> bool:

    tokens = search.split()

    # Ignore patterns
    ignore_patterns = [
        r"(19|20)\d{2}",      # year
        r"s\d{1,2}",          # s01
        r"season\d{1,2}",     # season1
        r"e\d{1,2}",          # e01
        r"ep\d{1,2}",         # ep01
    ]

    # Common standalone junk words
    junk_words = {
        "hindi", "english", "eng", "tamil", "telugu",
        "malayalam", "bangla", "bengali",
        "dubbed", "original", "dual", "multi",
        "480p", "720p", "1080p", "2160p", "4k",
        "hdrip", "webrip", "webdl", "bluray",
        "cam", "hdcam", "hq"
    }

    meaningful = False

    for token in tokens:

        # If token is junk word
        if token in junk_words:
            continue

        # If token matches ignore pattern
        matched = False
        for pattern in ignore_patterns:
            if re.fullmatch(pattern, token):
                matched = True
                break

        if matched:
            continue

        # If token has letters → meaningful
        if re.search(r"[a-zA-Z]", token) or re.fullmatch(r"\d{1,4}", token):
            meaningful = True
            break

    return meaningful


async def auto_memory_cleaner():
    while True:
        await asyncio.sleep(900)
        try:
            SPELL_CACHE.clear()
            POSTER_CACHE.clear()
            if hasattr(temp, "GETALL"):
                temp.GETALL.clear()
            if hasattr(temp, "SMART_FILTERS"):
                temp.SMART_FILTERS.clear()
        except:
            pass

def clean_query(text: str) -> str:
    if not text:
        return ""

    # remove markdown/special chars
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)

    # remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def smart_match(query, titles):

    query_l = query.lower()

    # 1️⃣ exact
    for t in titles:
        if t.lower() == query_l:
            return t

    # 2️⃣ startswith
    for t in titles:
        if t.lower().startswith(query_l):
            return t

    # 3️⃣ contains
    for t in titles:
        if query_l in t.lower():
            return t

    # 4️⃣ very light fuzzy (only few items)
    try:
        best = process.extractOne(query, titles)
        if best and best[1] >= 70:
            return best[0]
    except:
        pass

    return None

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    bot_id = client.me.id

    if message.text and message.text.lower().startswith(("#request", "/request")):
        return
		
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception:
            pass
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    user_id = message.from_user.id if message.from_user else None

    if user_id:
        await silentdb.update_top_messages(user_id, message.text)
    if message.chat.id != SUPPORT_CHAT_ID:
        settings = await get_settings(message.chat.id)
        if settings['auto_ffilter']:
            if re.search(r'https?://\S+|www\.\S+|t\.me/\S+', message.text):
                if await is_check_admin(client, message.chat.id, message.from_user.id):
                    return
                return await message.delete()   
            await auto_filter(client, message)
    else:
        search = message.text
        temp_files, temp_offset, total_results = await get_search_results(chat_id=message.chat.id, query=search.lower(), offset=0, filter=True)
        if total_results == 0:
            return
        else:
            return await message.reply_text(f"<b>Hᴇʏ {message.from_user.mention},\n\nʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ✅\n\n📂 ꜰɪʟᴇꜱ ꜰᴏᴜɴᴅ : {str(total_results)}\n🔍 ꜱᴇᴀʀᴄʜ :</b> <code>{search}</code>\n\n<b>‼️ ᴛʜɪs ɪs ᴀ <u>sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ</u> sᴏ ᴛʜᴀᴛ ʏᴏᴜ ᴄᴀɴ'ᴛ ɢᴇᴛ ғɪʟᴇs ғʀᴏᴍ ʜᴇʀᴇ...\n\n📝 ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ : 👇</b>",   
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 ᴊᴏɪɴ ᴀɴᴅ ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ 🔎", url=GRP_LNK)]]))


@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(bot, message):
    bot_id = bot.me.id
    content = message.text

    if not message.from_user:
        return

    user = message.from_user.first_name
    user_id = message.from_user.id

    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception:
            pass

    maintenance_mode = await db.get_maintenance_status(bot_id)

    if maintenance_mode and user_id not in ADMINS:
        await message.reply_text(
            "ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜",
            disable_web_page_preview=True
        )
        return

    if content.startswith(("/", "#")):
        return

    try:
        await silentdb.update_top_messages(user_id, content)

        pm_search = await db.pm_search_status(bot_id)

        # 🔐 Admin bypass (Admins can always search)
        if pm_search or user_id in ADMINS:
            await auto_filter(bot, message)
        else:
            await message.reply_text(
                text=(
                    "<b><i>Sᴏʀʀʏ! Yᴏᴜ Cᴀɴɴ'ᴛ Sᴇᴀʀᴄʜ Hᴇʀᴇ 🚫.\n"
                    "Jᴏɪɴ Tʜᴇ Rᴇǫᴜᴇsᴛ Gʀᴏᴜᴘ Fʀᴏᴍ Bᴇʟᴏᴡ Bᴜᴛᴛᴏɴ "
                    "Aɴᴅ Sᴇᴀʀᴄʜ Tʜᴇʀᴇ!</i></b>"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📝 Rᴇǫᴜᴇsᴛ Gʀᴏᴜᴘ", url=GRP_LNK)]]
                )
            )

    except Exception as e:
        LOGGER.error(f"An error occurred in pm_text: {str(e)}")

@Client.on_callback_query(filters.regex(r"^reffff"))
async def refercall(bot, query):
    btn = [[
        InlineKeyboardButton('ɪɴᴠɪᴛᴇ ɪɪɴᴋ', url=f'https://telegram.me/share/url?url=https://t.me/{bot.me.username}?start=reff_{query.from_user.id}&text=Hello%21%20Experience%20a%20bot%20that%20offers%20a%20vast%20library%20of%20unlimited%20movies%20and%20series.%20%F0%9F%98%83'),
        InlineKeyboardButton(f'⏳ {referdb.get_refer_points(query.from_user.id)}', callback_data='ref_point'),
        InlineKeyboardButton('ʙᴀᴄᴋ', callback_data='premium')
    ]]
    reply_markup = InlineKeyboardMarkup(btn)
    await bot.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto("https://i.ibb.co/spyQ29ry/photo-2025-12-12-14-23-10-7582976923882487832.jpg")
        )
    await query.message.edit_text(
        text=f'Hay Your refer link:\n\nhttps://t.me/{bot.me.username}?start=reff_{query.from_user.id}\n\nShare this link with your friends, Each time they join,  you will get 10 refferal points and after 100 points you will get 1 month premium subscription.',
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
        )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    try:
        ident, req, key, offset = query.data.split("_")
        # MULTI SELECT MODE
        if temp.MULTI_SELECT.get(key):
            offset = int(offset)
            await build_multi_page(bot, query, key, offset)
            return
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        if int(req) not in [query.from_user.id, 0]:
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        try:
            offset = int(offset)
        except:
            offset = 0
        if BUTTONS.get(key)!=None:
            search = BUTTONS.get(key)
        else:
            search = FRESH.get(key)
        if not search:
            await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
            return
        active = temp.ACTIVE_FILTER.get(key)
        settings = await get_settings(query.message.chat.id)
        per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)
        #active = temp.ACTIVE_FILTER.get(key)

        if active:
            # 🔹 FILTERED PAGINATION MODE
            all_files = temp.FILTER_FILES.get(key) or temp.GETALL.get(key, [])

            if active["type"] == "quality":
                data = [
                    f for f in all_files
                    if active["value"].lower() in (f.file_name or "").lower()
                ]

            elif active["type"] == "season":
                data = [
                    f for f in all_files
                    if active["value"].lower() in (f.file_name or "").lower()
                ]

            elif active["type"] == "language":
                aliases = SMART_LANG_MAP.get(active["value"], {}).get("aliases", [])
                data = [
                    f for f in all_files
                    if any(a in (f.file_name or "").lower() for a in aliases)
                ]
            elif active["type"] == "combined":
                data = temp.SMART_FILTERS.get(key, {}).get("combined") or []
	
            total = len(data)
            files = data[offset: offset + per_page]

            if total > offset + per_page:
                n_offset = offset + per_page
            else:
                n_offset = 0

        else:
            # 🔹 NORMAL HOMEPAGE PAGINATION MODE (use stored results)
            all_files = temp.GETALL.get(key) or files

            total = len(all_files)
            files = all_files[offset: offset + per_page]

            if total > offset + per_page:
                n_offset = offset + per_page
            else:
                n_offset = 0
            # normalize n_offset
        try:
            n_offset = int(n_offset)
        except:
            n_offset = 0

        if not files:
            return
        #temp.GETALL[key] = files
        temp.SHORT[query.from_user.id] = query.message.chat.id
        settings = await get_settings(query.message.chat.id)
        if settings.get('button'):
            btn = [
                [
                    InlineKeyboardButton(
                        text=f"{silent_size(file.file_size)} ✦ {extract_tag(file.file_name)} {clean_filename(file.file_name)}", callback_data=f'file#{file.file_id}'
                    ),
                ]
                for file in files
            ]
            combined_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []
            has_seasons = temp.SMART_FILTERS.get(key, {}).get("seasons")

            top_row = [
                InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
                InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
                InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0")
            ]

            btn.insert(0, top_row)

            if combined_files:
                btn.insert(1, [
                    InlineKeyboardButton("ᴄᴏᴍʙɪɴᴇᴅ", callback_data=f"fc#{key}#0"),
                    InlineKeyboardButton("ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ", callback_data=f"ms#{key}#{offset}")
                ])
            else:
                btn.insert(1, [
                    InlineKeyboardButton("ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ", callback_data=f"ms#{key}#{offset}")
                ])       
        else:
            combined_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []
            has_seasons = temp.SMART_FILTERS.get(key, {}).get("seasons")

            btn = []

            top_row = [
                InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
                InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
                InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0")
            ]

            btn.insert(0, top_row)

            if combined_files:
                btn.insert(1, [
                    InlineKeyboardButton("ᴄᴏᴍʙɪɴᴇᴅ", callback_data=f"fc#{key}#0"),
                    InlineKeyboardButton("ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ", callback_data=f"ms#{key}#{offset}")
                ])
            else:
                btn.insert(1, [
                    InlineKeyboardButton("ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ", callback_data=f"ms#{key}#{offset}")
                ])
            
        try:
            if settings['max_btn']:
                if 0 < offset <= 10:
                    off_set = 0
                elif offset == 0:
                    off_set = None
                else:
                    off_set = offset - 10
                if n_offset == 0:
                    btn.append(
                        [InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
                    )
                elif off_set is None:
                    btn.append([InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")])
                else:
                    btn.append(
                        [
                            InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
                            InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                            InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")
                        ],
                    )
            else:
                if 0 < offset <= int(MAX_B_TN):
                    off_set = 0
                elif offset == 0:
                    off_set = None
                else:
                    off_set = offset - int(MAX_B_TN)
                if n_offset == 0:
                    btn.append(
                        [InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages")]
                    )
                elif off_set is None:
                    btn.append([InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"), InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")])
                else:
                    btn.append(
                        [
                            InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
                            InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"),
                            InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")
                        ],
                    )
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            if 0 < offset <= 10:
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - 10
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                        InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
        active = temp.ACTIVE_FILTER.get(key)

        if active:
            if active["type"] == "language":
                btn.append([
                    InlineKeyboardButton("⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"fl#homepage#{key}#0")
                ])
            elif active["type"] == "season":
                btn.append([
                    InlineKeyboardButton("⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"fs#homepage#{key}#0")
                ])
            elif active["type"] == "quality":
                btn.append([
                    InlineKeyboardButton("⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"fq#homepage#{key}#0")
                ])
            elif active["type"] == "combined":
                btn.append([
                    InlineKeyboardButton("⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"fl#homepage#{key}#0")
                ])
        if not settings.get('button'):
            cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
            time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
            remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
            cap = await get_cap(settings, remaining_seconds, files, query, total, search, offset)
            try:
                await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
        else:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except MessageNotModified:
                pass
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Next Funtion - {e}")

# ================= MULTI SELECT SYSTEM =================

@Client.on_callback_query(filters.regex("^ms#"))
async def start_multi_select(client, query):

    _, key, offset = query.data.split("#")

    try:
        offset = int(offset)
    except:
        offset = 0

    owner_id = temp.OWNER.get(key)

    if not owner_id or query.from_user.id != owner_id:
        return await query.answer(
            "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
            show_alert=True
	    )
    if key not in temp.GETALL:
        return await query.answer(
            "⚠️ This session expired.\nPlease search again.",
            show_alert=True
        )

    # activate multi select mode
    temp.MULTI_SELECT[key] = True

    # ensure selection storage exists
    temp.MULTI_FILES.setdefault(key, set())

    all_files = temp.FILTER_FILES.get(key) or temp.GETALL.get(key, [])

    await query.answer()  # close loading spinner

    await build_multi_page(client, query, key, offset)

async def build_multi_page(client, query, key, offset):

    settings = await get_settings(query.message.chat.id)
    per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

    all_files = temp.FILTER_FILES.get(key) or temp.GETALL.get(key, [])
    total = len(all_files)

    files = all_files[offset: offset + per_page]

    if total > offset + per_page:
        n_offset = offset + per_page
    else:
        n_offset = None

    selected = temp.MULTI_FILES.setdefault(key, set())
    count = len(selected)

    btn = []

    # SEND + CANCEL
    btn.append([
        InlineKeyboardButton(
            f"ꜱᴇɴᴅ ({count})",
            callback_data=f"msend#{key}"
        ),
        InlineKeyboardButton(
            "ᴄᴀɴᴄᴇʟ",
            callback_data=f"mcancel#{key}"
        )
    ])

    # FILE LIST
    for f in files:

        fid = str(f.file_id)

        mark = "☑" if str(f.file_id) in selected else "☐"

        btn.append([
            InlineKeyboardButton(
                text=f"{mark} {silent_size(f.file_size)} ✦ {clean_filename(f.file_name)}",
                callback_data=f"mfile#{key}#{fid}#{offset}"
            )
        ])

    # PAGINATION
    page = (offset // per_page) + 1
    pages = math.ceil(total / per_page)

    nav = []

    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                "≪ ʙᴀᴄᴋ",
                callback_data=f"ms#{key}#{offset-per_page}"
            )
        )

    nav.append(
        InlineKeyboardButton(
            f"{page}/{pages}",
            callback_data="pages"
        )
    )

    if n_offset is not None:
        nav.append(
            InlineKeyboardButton(
                "ɴᴇxᴛ ≫",
                callback_data=f"ms#{key}#{n_offset}"
            )
        )

    if nav:  # prevent empty row
        btn.append(nav)

    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except Exception:
        pass
    


# ================= SELECT / UNSELECT =================

@Client.on_callback_query(filters.regex("^mfile#"))
async def toggle_multi_file(client, query):

    _, key, fid, offset = query.data.split("#")

    try:
        offset = int(offset)
    except:
        offset = 0

    owner_id = temp.OWNER.get(key)

    if not owner_id or query.from_user.id != owner_id:
        return await query.answer(
            "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
            show_alert=True
        )

    fid = str(fid)

    if key not in temp.GETALL:
        return await query.answer(
            "⚠️ This session expired.\nPlease search again.",
            show_alert=True
        )

    selected = temp.MULTI_FILES.setdefault(key, set())

    valid_ids = {str(f.file_id) for f in temp.GETALL.get(key, [])}

    if fid not in valid_ids:
        return

    if len(selected) >= 15 and fid not in selected:
        return await query.answer(
            "⚠️ Maximum 15 files allowed",
            show_alert=True
        )

    if fid in selected:
        selected.remove(fid)
    else:
        selected.add(fid)

    await query.answer()

    await build_multi_page(client, query, key, offset)


#================= SEND FILES =================

@Client.on_callback_query(filters.regex("^msend#"))
async def send_multi_files(client, query):

    from plugins.commands import send_file_pipeline

    _, key = query.data.split("#")

    owner_id = temp.OWNER.get(key)

    if not owner_id or query.from_user.id != owner_id:
        return await query.answer(
            "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
            show_alert=True
        )

    if key not in temp.GETALL:
        return await query.answer(
            "⚠️ Session expired. Please search again.",
            show_alert=True
        )

    user_id = query.from_user.id
    grp_id = query.message.chat.id

    selected = list(temp.MULTI_FILES.get(key, set()))

    if not selected:
        return await query.answer(
            "⚠️ ʏᴏᴜ ᴅɪᴅɴ'ᴛ sᴇʟᴇᴄᴛ ᴀɴʏ ғɪʟᴇs",
            show_alert=True
        )

    # check if user started bot
    try:
        await client.send_chat_action(user_id, "typing")
    except:

        temp.PENDING_MULTI[user_id] = {
            "files": selected,
            "grp_id": grp_id
        }

        return await query.answer(
            url=f"https://t.me/{temp.U_NAME}?start=multifile"
        )

    # popup alert
    await query.answer(
        "✅ sᴇʟᴇᴄᴛᴇᴅ ғɪʟᴇs ᴀʀᴇ sᴜᴄᴄᴇssғᴜʟʟʏ sᴇɴᴛ ᴛᴏ ʏᴏᴜʀ ᴘᴍ.\n\nɢᴏ ʙᴀᴄᴋ & ᴄʜᴇᴄᴋ ʙᴏᴛ ᴍᴀssᴀɢᴇ !",
        show_alert=True
    )

    # clear selection first
    temp.MULTI_FILES.pop(key, None)
    temp.MULTI_SELECT.pop(key, None)

    temp.PAGE_STATE[key] = {
        "current_offset": 0
	}
    # restore main result page
    try:
        # force remove select UI first
        await query.message.edit_reply_markup(None)
        await asyncio.sleep(0.2)

        # load main result page
        await restore_main_page(client, query, key)

    except Exception as e:
        print("Restore UI error:", e)

    # send files
    for fid in selected:

        try:
            await send_file_pipeline(
                client,
                query,
                str(fid),
                grp_id
            )

            await asyncio.sleep(0.25)

        except Exception as e:
            print("Multi send error:", e)


#================= CANCEL =================

@Client.on_callback_query(filters.regex("^mcancel#"))
async def cancel_multi_select(client, query):

    _, key = query.data.split("#")

    owner_id = temp.OWNER.get(key)

    if not owner_id or query.from_user.id != owner_id:
        return await query.answer(
            "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
            show_alert=True
		)

    temp.MULTI_FILES.pop(key, None)
    temp.MULTI_SELECT.pop(key, None)

    await query.answer("sᴇʟᴇᴄᴛɪᴏɴ ᴄᴀɴᴄᴇʟᴇᴅ..")

    await restore_main_page(client, query, key)


async def restore_main_page(client, query, key):

    if key not in temp.GETALL:
        return

    all_files = temp.GETALL.get(key, [])

    settings = await get_settings(query.message.chat.id)
    per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

    offset = int(temp.PAGE_STATE.get(key, {}).get("current_offset", 0))

    files = all_files[offset: offset + per_page]
    total = len(all_files)


    req = query.from_user.id

    btn = [
        [
            InlineKeyboardButton(
                text=f"{silent_size(f.file_size)} ✦ {extract_tag(f.file_name)} {clean_filename(f.file_name)}",
                callback_data=f"file#{f.file_id}"
            )
        ]
        for f in files
    ]

    combined_files = bool(temp.SMART_FILTERS.get(key, {}).get("combined"))

    btn.insert(0, [
        InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
        InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0")
    ])
    if combined_files:
        btn.insert(1, [
            InlineKeyboardButton("ᴄᴏᴍʙɪɴᴇᴅ", callback_data=f"fc#{key}#0"),
            InlineKeyboardButton("ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ", callback_data=f"ms#{key}#{offset}")
        ])
    else:
        btn.insert(1, [
            InlineKeyboardButton("ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ", callback_data=f"ms#{key}#{offset}")
        ])

    # pagination
    if total > offset + per_page:

        total_pages = math.ceil(total / per_page)

        btn.append([
            InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
            InlineKeyboardButton(f"1/{total_pages}", callback_data="pages"),
            InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{per_page}")
        ])

    else:

        btn.append([
            InlineKeyboardButton(
                "↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭",
                callback_data="pages"
            )
        ])

    await query.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(btn)
	)
    

# ================= OLD QUALITY CALLBACK =================
async def old_qualities_cb(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [
                query.message.reply_to_message.from_user.id, 0
            ]:
                return await query.answer(
                    f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\n"
                    f"ᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ,\n"
                    f"ʀᴇǫᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                    show_alert=True,
                )
        except:
            pass

        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        search = search.replace(" ", "_")
        offset = int(offset)

        btn = []
        for i in range(0, len(QUALITIES) - 1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=QUALITIES[i].title(),
                    callback_data=f"fq#{QUALITIES[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=QUALITIES[i + 1].title(),
                    callback_data=f"fq#{QUALITIES[i + 1].lower()}#{key}#{offset}"
                ),
            ])

        btn.insert(0, [
            InlineKeyboardButton(
                text="⇊ ꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ ⇊",
                callback_data="ident"
            )
        ])

        btn.append([
            InlineKeyboardButton(
                text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ↭",
                callback_data=f"fq#homepage#{key}#0"
            )
        ])

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(btn)
        )

    except Exception as e:
        LOGGER.error(f"Error In Old Quality Callback - {e}")


# ================= SMART QUALITY CALLBACK =================
# ================= SMART QUALITY CALLBACK =================
async def smart_qualities_cb(client: Client, query: CallbackQuery):
    try:
        _, key, offset = query.data.split("#")
        offset = int(offset)

        # 🔐 STRICT OWNERSHIP CHECK (ADD HERE)
        owner_id = temp.OWNER.get(key)

        if owner_id is None:
             return await query.answer(
                "❌ Session expired, please search again",
                show_alert=True
            )

        if query.from_user.id != owner_id:
             return await query.answer(
                "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
                show_alert=True
			 )
        if key not in temp.SMART_FILTERS:
            return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ.",
                show_alert=True
            )

        qualities = temp.SMART_FILTERS[key].get("qualities", [])
        all_files = temp.GETALL.get(key, [])

        if not qualities:
            return await query.answer(
                "sᴏʀʀʏ!!\nǫᴜᴀʟɪᴛʏ ɪs ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜɪs ʀᴇsᴜʟᴛ.",
                show_alert=True
            )

        # 🔹 Only button view (no filter yet)
        btn = []
        for i in range(0, len(qualities), 2):
            row = [
                InlineKeyboardButton(
                    qualities[i].upper(),
                    callback_data=f"fq#{qualities[i]}#{key}#0"
                )
            ]
            if i + 1 < len(qualities):
                row.append(
                    InlineKeyboardButton(
                        qualities[i + 1].upper(),
                        callback_data=f"fq#{qualities[i + 1]}#{key}#0"
                    )
                )
            btn.append(row)

        btn.insert(0, [
            InlineKeyboardButton("⇊ ꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ ⇊", callback_data="ident")
        ])

        btn.append([
            InlineKeyboardButton("⋞ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs", callback_data=f"fq#homepage#{key}#0")
        ])

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(btn)
        )

    except Exception as e:
        LOGGER.error(f"Error In Smart Quality Callback - {e}")

# ================= QUALITY ROUTER =================
@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_router(client: Client, query: CallbackQuery):
    if SMART_SELECTION_MODE:
        return await smart_qualities_cb(client, query)
    return await old_qualities_cb(client, query)

@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, qual, key, _ = query.data.split("#")
        offset = 0

         # 🔐 STRICT OWNERSHIP CHECK (ADD HERE)
        owner_id = temp.OWNER.get(key)

        if owner_id is None:
             return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        if query.from_user.id != owner_id:
             return await query.answer(
                "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
                show_alert=True
			 )

        message = query.message
        chat_id = message.chat.id
        req = query.from_user.id

        # 🔐 Ownership check
       # try:
           # if int(query.from_user.id) not in [message.reply_to_message.from_user.id, 0]:
               # return await query.answer(
                 #   f"⚠️ Hello {query.from_user.first_name}, this is not your request.",
                   # show_alert=True,
               # )
        #except:
            #pass

        search = FRESH.get(key, "").replace("_", " ")
        BUTTONS[key] = search
        # ================= SAVE ACTIVE FILTER STATE =================
        if not hasattr(temp, "ACTIVE_FILTER"):
            temp.ACTIVE_FILTER = {}

        if qual == "homepage":
            # homepage এ গেলে filter clear
            temp.ACTIVE_FILTER.pop(key, None)
        else:
            # quality filter active
            temp.ACTIVE_FILTER[key] = {
                "type": "quality",
                "value": qual
            }
# ============================================================
        # ================= SMART MODE =================
        if SMART_SELECTION_MODE:
            #offset = 0   # ⬅️ IMPORTANT
            all_files = temp.GETALL.get(key, [])

            # 🔁 BACK TO MAIN FILE LIST
            if qual == "homepage":
                temp.FILTER_FILES.pop(key, None)
                settings = await get_settings(chat_id)
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                total_results = len(all_files)
                files = all_files[offset: offset + per_page]

                if total_results > offset + per_page:
                    n_offset = offset + per_page
                else:
                    n_offset = ""
            # 🔍 FILTER MODE (quality selected)
            else:
                offset = 0
                # 1️⃣ সব ফাইল থেকে filter করো
                filtered_files = [
                    f for f in all_files
                    if qual.lower() in (f.file_name or "").lower()
                ]
                temp.FILTER_FILES[key] = filtered_files
				
                total_results = len(filtered_files)

                settings = await get_settings(chat_id)
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                # 2️⃣ filter করলে সবসময় first page থেকে শুরু
                offset = 0
                files = filtered_files[:per_page]

                # ⭐⭐⭐ EXACTLY HERE ⭐⭐⭐
                temp.PAGE_STATE[key] = {
                    "total_results": total_results,
                    "per_page": per_page,
                    "current_offset": offset
	            }
                # 3️⃣ pagination decide করো
                if total_results > per_page:
                    n_offset = per_page
                else:
                    n_offset = ""   # 👈 এইখানেই "no more page available" trigger হবে   # ❌ no pagination in filter mode

            if not files:
                # 🔁 homepage এ গেলে popup না দেখাও
                if SMART_SELECTION_MODE and qual == "homepage":
                    files = all_files
                else:
                    return await query.answer(
                        "🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫",
                        show_alert=True
					)

        # ================= OLD MODE =================
        else:
            if qual != "homepage":
                search = f"{search} {qual}"

            files, n_offset, total_results = await get_search_results(
                chat_id,
                search,
                offset=offset,
                filter=True
            )

            if not files:
                return await query.answer(
                    "🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫",
                    show_alert=True
                )


        # ================= BUILD FILE BUTTONS =================
        settings = await get_settings(chat_id)

        btn = [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(f.file_size)} ✦ {extract_tag(f.file_name)} {clean_filename(f.file_name)}",
                    callback_data=f"file#{f.file_id}"
                )
            ]
            for f in files
        ]

        # 🔝 Top filter buttons
        btn.insert(0, [
            InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
            InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0"),
        ])
        combined_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []

        if combined_files:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ᴄᴏᴍʙɪɴᴇᴅ",
                    callback_data=f"fc#{key}#0"
                ),
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])
        else:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])
        # 🔽 Pagination (old mode OR restored homepage)
        if n_offset != "":
            try:
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)
                current_page = (offset // per_page) + 1
                total_pages = math.ceil(total_results / per_page)
                btn.append([
                    InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
                    InlineKeyboardButton(
                        text=f"{current_page}/{total_pages}",
                        callback_data="pages"
                    ),
                    InlineKeyboardButton(
                        "ɴᴇxᴛ ⋟",
                        callback_data=f"next_{req}_{key}_{n_offset}"
                    )
                ])
            except:
                pass
        else:
            # ℹ️ single page info
            btn.append([
                InlineKeyboardButton(
                    text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭",
                    callback_data="pages"
                )
            ])
        if qual != "homepage":
            btn.append([
                InlineKeyboardButton(
                    text="⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ",
                    callback_data=f"fq#homepage#{key}#0"
                )
            ])
        # ================= SEND UPDATE =================
        try:
            if settings.get("button"):
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            else:
                cap = await get_cap(
                    settings,
                    "0",
                    files,
                    query,
                    total_results,
                    search,
                    offset
                )
                await query.message.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
        except MessageNotModified:
            pass

        await query.answer()

    except Exception as e:
        LOGGER.error(f"Error In Quality Filter - {e}")
# ================= OLD LANGUAGE CALLBACK =================
#================= OLD LANGUAGE CALLBACK =================
async def old_languages_cb(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [
                query.message.reply_to_message.from_user.id, 0
            ]:
                return await query.answer(
                    f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\n"
                    f"ᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ,\n"
                    f"ʀᴇǫᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                    show_alert=True,
                )
        except:
            pass

        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        if not search:
            return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        offset = int(offset)

        btn = []
        for i in range(0, len(LANGUAGES) - 1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=LANGUAGES[i].title(),
                    callback_data=f"fl#{LANGUAGES[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=LANGUAGES[i + 1].title(),
                    callback_data=f"fl#{LANGUAGES[i + 1].lower()}#{key}#{offset}"
                ),
            ])

        btn.insert(0, [
            InlineKeyboardButton(
                text="⇊ ꜱᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ ⇊",
                callback_data="ident"
            )
        ])

        btn.append([
            InlineKeyboardButton(
                text="⋞ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs",
                callback_data=f"fl#homepage#{key}#0"
            )
        ])

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(btn)
        )

    except Exception as e:
        LOGGER.error(f"Error In Old Language Callback - {e}")


# ================= SMART LANGUAGE CALLBACK =================
async def smart_languages_cb(client: Client, query: CallbackQuery):
    try:
        _, key, offset = query.data.split("#")
        offset = int(offset)

        # 🔐 STRICT OWNERSHIP CHECK (ADD HERE)
        owner_id = temp.OWNER.get(key)

        if owner_id is None:
             return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        if query.from_user.id != owner_id:
             return await query.answer(
                "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
                show_alert=True
			 )
        if key not in temp.SMART_FILTERS:
            return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        languages = temp.SMART_FILTERS[key].get("languages", [])

        if not languages:
            return await query.answer(
                "❌ No language available",
                show_alert=True
            )

        btn = []
        for i in range(0, len(languages), 2):
            row = [
                InlineKeyboardButton(
                    SMART_LANG_MAP[languages[i]]["label"],
                    callback_data=f"fl#{languages[i]}#{key}#{offset}"
                )
            ]
            if i + 1 < len(languages):
                row.append(
                    InlineKeyboardButton(
                        SMART_LANG_MAP[languages[i + 1]]["label"],
                        callback_data=f"fl#{languages[i + 1]}#{key}#{offset}"
                    )
                )
            btn.append(row)

        btn.insert(0, [
            InlineKeyboardButton(
                text="⇊ ꜱᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ ⇊",
                callback_data="ident"
            )
        ])

        btn.append([
            InlineKeyboardButton(
                text="⋞ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs",
                callback_data=f"fl#homepage#{key}#0"
            )
        ])

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(btn)
        )

    except Exception as e:
        LOGGER.error(f"Error In Smart Language Callback - {e}")


# ================= LANGUAGE ROUTER =================
@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_router(client: Client, query: CallbackQuery):
    if SMART_SELECTION_MODE:
        return await smart_languages_cb(client, query)
    return await old_languages_cb(client, query)

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_language_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, lang, key, _ = query.data.split("#")
        offset = 0

        # 🔐 STRICT OWNERSHIP CHECK (ADD HERE)
        owner_id = temp.OWNER.get(key)

        if owner_id is None:
             return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        if query.from_user.id != owner_id:
             return await query.answer(
                "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
                show_alert=True
			 )

        message = query.message
        chat_id = message.chat.id
        req = query.from_user.id

        # 🔐 Ownership check
        #try:
            #if int(query.from_user.id) not in [message.reply_to_message.from_user.id, 0]:
                #return await query.answer(
                    #f"⚠️ Hello {query.from_user.first_name}, this is not your request.",
                   # show_alert=True,
                #)
       # except:
           # pass
        # ================= SAVE ACTIVE FILTER STATE =================
        if not hasattr(temp, "ACTIVE_FILTER"):
            temp.ACTIVE_FILTER = {}

        if lang == "homepage":
            temp.ACTIVE_FILTER.pop(key, None)
        else:
            temp.ACTIVE_FILTER[key] = {
                "type": "language",
                "value": lang
			}
        search = FRESH.get(key, "").replace("_", " ")
        BUTTONS[key] = search

        # ================= SMART MODE =================
        if SMART_SELECTION_MODE:
            #offset = 0   # ⬅️ IMPORTANT
            all_files = temp.GETALL.get(key, [])

            # 🔁 BACK TO MAIN FILE LIST
            if lang == "homepage":
                temp.FILTER_FILES.pop(key, None)
                settings = await get_settings(chat_id)
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                total_results = len(all_files)
                files = all_files[offset: offset + per_page]

                if total_results > offset + per_page:
                    n_offset = offset + per_page
                else:
                    n_offset = ""
            # 🔍 FILTER MODE (quality selected)
            else:
                offset = 0
                aliases = SMART_LANG_MAP.get(lang, {}).get("aliases", [])
                # 1️⃣ সব ফাইল থেকে filter করো
                filtered_files = [
                    f for f in all_files
                    if any(alias in (f.file_name or "").lower() for alias in aliases)
				]

                temp.FILTER_FILES[key] = filtered_files

                total_results = len(filtered_files)

                settings = await get_settings(chat_id)
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                # 2️⃣ filter করলে সবসময় first page থেকে শুরু
                offset = 0
                files = filtered_files[:per_page]

                # ⭐⭐⭐ EXACTLY HERE ⭐⭐⭐
                temp.PAGE_STATE[key] = {
                    "total_results": total_results,
                    "per_page": per_page,
                    "current_offset": offset
				}
                # 3️⃣ pagination decide করো
                if total_results > per_page:
                    n_offset = per_page
                else:
                    n_offset = ""   # 👈 এইখানেই "no more page available" trigger হবে   # ❌ no pagination in filter mode
            if not files:
                # 🔁 homepage এ গেলে popup না দেখাও
                if SMART_SELECTION_MODE and lang == "homepage":
                    files = all_files
                else:
                    return await query.answer(
                        "🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫",
                        show_alert=True
					)
            
   # ❌ no pagination in filter mode

            #if not files:
                #return await query.answer(
                    #"🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫",
                    #show_alert=True
                #)

        # ================= OLD MODE =================
        else:
            if lang != "homepage":
                search = f"{search} {lang}"

            files, n_offset, total_results = await get_search_results(
                chat_id,
                search,
                offset=offset,
                filter=True
            )

            if not files:
                return await query.answer(
                    "🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫",
                    show_alert=True
                )


        # ================= BUILD FILE BUTTONS =================
        settings = await get_settings(chat_id)

        btn = [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(f.file_size)} ✦ {extract_tag(f.file_name)} {clean_filename(f.file_name)}",
                    callback_data=f"file#{f.file_id}"
                )
            ]
            for f in files
        ]

        # 🔝 Top filter buttons
        btn.insert(0, [
            InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
            InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0"),
        ])
        combined_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []

        if combined_files:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ᴄᴏᴍʙɪɴᴇᴅ",
                    callback_data=f"fc#{key}#0"
                ),
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])
        else:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])
        # 🔽 Pagination (ONLY old mode OR restored homepage)
        # 🔽 Pagination
        if n_offset != "":
            try:
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                current_page = (offset // per_page) + 1
                total_pages = math.ceil(total_results / per_page)

                btn.append([
                    InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
                    InlineKeyboardButton(
                        text=f"{current_page}/{total_pages}",
                        callback_data="pages"
                    ),
                    InlineKeyboardButton(
                        "ɴᴇxᴛ ⋟",
                        callback_data=f"next_{req}_{key}_{n_offset}"
                    )
                ])
            except:
                pass
        else:
            btn.append([
                InlineKeyboardButton(
                    text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭",
                    callback_data="pages"
                )
            ])
        # 🔙 Back to main file list
        if lang != "homepage":
            btn.append([
                InlineKeyboardButton(
                    text="⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ",
                    callback_data=f"fl#homepage#{key}#0"
                )
            ])
        # ================= SEND UPDATE =================
        try:
            if settings.get("button"):
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            else:
                cap = await get_cap(
                    settings,
                    "0",
                    files,
                    query,
                    total_results,
                    search,
                    offset
                )
                await query.message.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
        except MessageNotModified:
            pass

        await query.answer()

    except Exception as e:
        LOGGER.error(f"Error In Language Filter - {e}")

# ================= OLD SEASON CALLBACK =================
async def old_seasons_cb(client: Client, query: CallbackQuery):
    try:
        try:
            if int(query.from_user.id) not in [
                query.message.reply_to_message.from_user.id, 0
            ]:
                return await query.answer(
                    f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\n"
                    f"ᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ,\n"
                    f"ʀᴇǫᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                    show_alert=True,
                )
        except:
            pass

        _, key, offset = query.data.split("#")
        search = FRESH.get(key)
        search = search.replace(" ", "_")
        offset = int(offset)

        btn = []
        for i in range(0, len(SEASONS) - 1, 2):
            btn.append([
                InlineKeyboardButton(
                    text=SEASONS[i].title(),
                    callback_data=f"fs#{SEASONS[i].lower()}#{key}#{offset}"
                ),
                InlineKeyboardButton(
                    text=SEASONS[i + 1].title(),
                    callback_data=f"fs#{SEASONS[i + 1].lower()}#{key}#{offset}"
                ),
            ])

        btn.insert(0, [
            InlineKeyboardButton(
                text="⇊ ꜱᴇʟᴇᴄᴛ sᴇᴀsᴏɴ ⇊",
                callback_data="ident"
            )
        ])

        btn.append([
            InlineKeyboardButton(
                text="⋞ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs",
                callback_data=f"fl#homepage#{key}#0"
            )
        ])

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(btn)
        )

    except Exception as e:
        LOGGER.error(f"Error In Old Season Callback - {e}")


# ================= SMART SEASON CALLBACK =================
# ================= SMART SEASON CALLBACK =================
async def smart_seasons_cb(client: Client, query: CallbackQuery):
    try:
        _, key, offset = query.data.split("#")
        offset = int(offset)

        # 🔐 STRICT OWNERSHIP CHECK (ADD HERE)
        owner_id = temp.OWNER.get(key)

        if owner_id is None:
             return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        if query.from_user.id != owner_id:
             return await query.answer(
                "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
                show_alert=True
			 )
        if key not in temp.SMART_FILTERS:
            return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        data = temp.SMART_FILTERS[key].get("seasons", [])

        if not data:
            return await query.answer(
                "sᴇᴀsᴏɴ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜɪs ʀᴇsᴜʟᴛ",
                show_alert=True
            )

        btn = []
        for i in range(0, len(data), 2):
            row = [
                InlineKeyboardButton(
                    data[i],
                    callback_data=f"fs#{data[i].lower()}#{key}#{offset}"
                )
            ]
            if i + 1 < len(data):
                row.append(
                    InlineKeyboardButton(
                        data[i + 1],
                        callback_data=f"fs#{data[i + 1].lower()}#{key}#{offset}"
                    )
                )
            btn.append(row)

        btn.insert(0, [
            InlineKeyboardButton(
                "⇊ ꜱᴇʟᴇᴄᴛ sᴇᴀꜱᴏɴ ⇊",
                callback_data="ident"
            )
        ])

        btn.append([
            InlineKeyboardButton(
                "⋞ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs",
                callback_data=f"fl#homepage#{key}#0"
            )
        ])

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(btn)
        )

    except Exception as e:
        LOGGER.error(f"Error In Smart Season Callback - {e}")


# ================= SEASON ROUTER =================
@Client.on_callback_query(filters.regex(r"^seasons#"))
async def seasons_router(client: Client, query: CallbackQuery):
    if SMART_SELECTION_MODE:
        return await smart_seasons_cb(client, query)
    return await old_seasons_cb(client, query)


@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_season_cb_handler(client: Client, query: CallbackQuery):
    try:
        _, seas, key, _ = query.data.split("#")
        offset = 0

        # 🔐 STRICT OWNERSHIP CHECK (ADD HERE)
        # 🔐 STRICT OWNERSHIP CHECK (SAFE)
        owner_id = temp.OWNER.get(key)

        if owner_id is None:
             return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ,\nᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        if query.from_user.id != owner_id:
             return await query.answer(
                "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
                show_alert=True
	        )

        message = query.message
        chat_id = message.chat.id
        req = query.from_user.id

        # 🔐 Ownership check
        #try:
            #if int(query.from_user.id) not in [
                #message.reply_to_message.from_user.id, 0
            #]:
                #return await query.answer(
                    #f"⚠️ Hello {query.from_user.first_name}, this is not your request.",
                    #show_alert=True,
                #)
        #except:
            #pass

        # ================= SAVE ACTIVE FILTER STATE =================
        if not hasattr(temp, "ACTIVE_FILTER"):
            temp.ACTIVE_FILTER = {}

        if seas == "homepage":
            temp.ACTIVE_FILTER.pop(key, None)
        else:
            temp.ACTIVE_FILTER[key] = {
                "type": "season",
                "value": seas
            }
# ============================================================
        search = FRESH.get(key, "").replace("_", " ")
        BUTTONS[key] = search

        # ================= SMART MODE =================
        if SMART_SELECTION_MODE:
            #offset = 0   # ⬅️ IMPORTANT
            all_files = temp.GETALL.get(key, [])
            settings = await get_settings(chat_id)
            # 🔁 BACK TO MAIN FILE LIST
            if seas == "homepage":
                temp.FILTER_FILES.pop(key, None)
                settings = await get_settings(chat_id)
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                total_results = len(all_files)
                files = all_files[offset: offset + per_page]

                if total_results > offset + per_page:
                    n_offset = offset + per_page
                else:
                    n_offset = ""
            # 🔍 FILTER MODE (season selected)
            else:
                offset = 0
                filtered_files = [
                    f for f in all_files
                    if seas.lower() in (f.file_name or "").lower()
                ]

                temp.FILTER_FILES[key] = filtered_files
	
                total_results = len(filtered_files)

                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                offset = 0
                files = filtered_files[:per_page]

                temp.PAGE_STATE[key] = {
                    "total_results": total_results,
                    "per_page": per_page,
                    "current_offset": offset
				}
                if total_results > per_page:
                    n_offset = per_page
                else:
                    n_offset = ""   # ❌ no pagination in filter mode

            if not files:
                # 🔁 homepage এ গেলে popup না দেখাও
                if SMART_SELECTION_MODE and seas == "homepage":
                    files = all_files
                else:
                    return await query.answer(
                        "🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫",
                        show_alert=True
		            )

        # ================= OLD MODE =================
        else:
            if seas != "homepage":
                search = f"{search} {seas}"

            files, n_offset, total_results = await get_search_results(
                chat_id,
                search,
                offset=offset,
                filter=True
            )

            if not files:
                return await query.answer(
                    "🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫",
                    show_alert=True
                )

        # ================= BUILD RESULT BUTTONS =================
        settings = await get_settings(chat_id)

        btn = [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(f.file_size)} ✦ "
                         f"{extract_tag(f.file_name)}"
                         f"{clean_filename(f.file_name)}",
                    callback_data=f"file#{f.file_id}"
                )
            ]
            for f in files
        ]

        # 🔝 Top filter buttons
        btn.insert(0, [
            InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
            InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0"),
        ])
        combined_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []

        if combined_files:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ᴄᴏᴍʙɪɴᴇᴅ",
                    callback_data=f"fc#{key}#0"
                ),
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])
        else:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])

        # 🔽 Pagination
        if n_offset != "":
            try:
                per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

                current_page = (offset // per_page) + 1
                total_pages = math.ceil(total_results / per_page)

                btn.append([
                    InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"),
                    InlineKeyboardButton(
                        text=f"{current_page}/{total_pages}",
                        callback_data="pages"
                    ),
                    InlineKeyboardButton(
                        "ɴᴇxᴛ ⋟",
                        callback_data=f"next_{req}_{key}_{n_offset}"
                    )
                ])
            except:
                pass
        else:
            btn.append([
                InlineKeyboardButton(
                    text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭",
                    callback_data="pages"
                )
            ])
        if seas != "homepage":
            btn.append([
                InlineKeyboardButton(
                    text="⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ",
                    callback_data=f"fs#homepage#{key}#0"
                )
            ])
        # ================= SEND UPDATE =================
        try:
            if settings.get("button"):
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            else:
                cap = await get_cap(
                    settings,
                    "0",
                    files,
                    query,
                    total_results,
                    search,
                    offset
                )
                await query.message.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
        except MessageNotModified:
            pass

        await query.answer()

    except Exception as e:
        LOGGER.error(f"Error In Season Filter - {e}")

@Client.on_callback_query(filters.regex(r"^fc#"))
async def combined_filter(client, query):

    try:
        _, key, offset = query.data.split("#")

        try:
            offset = int(offset)
        except:
            offset = 0

        # 🔐 OWNER CHECK
        owner_id = temp.OWNER.get(key)

        if owner_id is None:
            return await query.answer(
                "❌ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ, ᴘʟᴇᴀsᴇ sᴇᴀʀᴄʜ ᴀɢᴀɪɴ",
                show_alert=True
            )

        if query.from_user.id != owner_id:
            return await query.answer(
                "🚫 ɴᴏᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʙᴜᴅᴅʏ !!",
                show_alert=True
            )

        await query.answer()

        # 🔹 ACTIVE FILTER STATE
        if not hasattr(temp, "ACTIVE_FILTER"):
            temp.ACTIVE_FILTER = {}

        temp.ACTIVE_FILTER[key] = {
            "type": "combined",
            "value": "combined"
        }

        # 🔹 GET COMBINED FILES
        all_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []

        temp.FILTER_FILES[key] = all_files

        total_packs = len(all_files)

        if not all_files:
            return await query.answer(
                "🚫 ɴᴏ ᴄᴏᴍʙɪɴᴇᴅ ꜰɪʟᴇꜱ ꜰᴏᴜɴᴅ",
                show_alert=True
            )

        chat_id = query.message.chat.id
        settings = await get_settings(chat_id)

        per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

        files = all_files[offset: offset + per_page]

        total_results = len(all_files)

        if total_results > offset + per_page:
            n_offset = offset + per_page
        else:
            n_offset = ""

        # ================= FILE BUTTONS =================
        # ================= FILE BUTTONS =================

        btn = []

        # 🔹 Combined Info Button (Top UI)
        btn.append([
            InlineKeyboardButton(
                f"⇊ ᴄᴏᴍʙɪɴᴇᴅ ꜰɪʟᴇꜱ • {len(all_files)} ᴘᴀᴄᴋꜱ ⇊",
                callback_data="combined_info"
            )
        ])
        btn.append([
            InlineKeyboardButton(
                "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                callback_data=f"ms#{key}#{offset}"
            )
        ])
        # 🔹 Combined Files List
        btn += [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(f.file_size)} ✦ {extract_tag(f.file_name)} {clean_filename(f.file_name)}",
                    callback_data=f"file#{f.file_id}"
                )
            ]
            for f in files
        ]

        # ================= PAGINATION =================
        current_page = (offset // per_page) + 1
        total_pages = math.ceil(total_results / per_page)

        prev_offset = offset - per_page if offset > 0 else None

        row = []

        if prev_offset is not None:
            row.append(
                InlineKeyboardButton(
                    "⋞ ʙᴀᴄᴋ",
                    callback_data=f"fc#{key}#{prev_offset}"
                )
            )

        row.append(
            InlineKeyboardButton(
                text=f"{current_page}/{total_pages}",
                callback_data="pages"
            )
        )

        if n_offset != "":
            row.append(
                InlineKeyboardButton(
                    "ɴᴇxᴛ ⋟",
                    callback_data=f"fc#{key}#{n_offset}"
                )
            )

        btn.append(row)

        # 🔙 BACK TO MAIN PAGE
        btn.append([
            InlineKeyboardButton(
                text="⋞ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ",
                callback_data=f"fl#homepage#{key}#0"
            )
        ])

        # ================= UPDATE MESSAGE =================
        # ================= UPDATE MESSAGE =================
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except MessageNotModified:
            pass

            
    except Exception as e:
        LOGGER.error(f"Error In Combined Filter - {e}")

@Client.on_callback_query(filters.regex("^combined_info$"))
async def combined_info_popup(client, query):

    user = query.from_user
    chat_id = query.message.chat.id

    # 🔹 Detect current search session
    key = None
    try:
        msg_id = query.message.reply_to_message.id
        key = f"{chat_id}-{msg_id}"
    except:
        pass

    packs = 0
    if key:
        packs = len(temp.SMART_FILTERS.get(key, {}).get("combined", []))

    text = (
        f"👋 ʜᴇʏ {user.first_name}\n\n"
        f"📊 ᴛᴏᴛᴀʟ ᴄᴏᴍʙɪɴᴇᴅ ᴘᴀᴄᴋꜱ : {packs}\n\n"
        f"📂 ᴛʜᴇꜱᴇ ꜰɪʟᴇꜱ ᴍᴀʏ ɪɴᴄʟᴜᴅᴇ\n"
        f"• ᴍᴜʟᴛɪᴘʟᴇ ᴇᴘɪꜱᴏᴅᴇꜱ\n"
        f"• ᴄᴏᴍᴘʟᴇᴛᴇ ꜱᴇᴀꜱᴏɴ ᴘᴀᴄᴋ\n"
        f"• ꜰᴜʟʟ ꜱᴇʀɪᴇꜱ ᴘᴀᴄᴋ\n\n"
    )

    await query.answer(text, show_alert=True)

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):

    _, id, user = query.data.split('#')

    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(
            script.ALRT_TXT.format(query.from_user.first_name),
            show_alert=True
        )
    try:
        movies = await get_poster(id, id=True)
        title = movies.get("title") if isinstance(movies, dict) else None
        movie = clean_query(title) if title else None
    except Exception:
        movies = None
        movie = None
    if not movie:
        return await query.answer(
            f"sᴏʀʀʏ {query.from_user.first_name},\n"
            f"ᴄᴏᴜʟᴅɴ'ᴛ ғɪɴᴅ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ:\n{clean_query(id)}",
            show_alert=True
	    )
    await query.answer(script.TOP_ALRT_MSG)
    
    chat_id = query.message.chat.id
    spell_msg = query.message          # 🔥 save spelling list message
    user_msg = query.message.reply_to_message

    # 🔥 delete spelling list
    try:
        await spell_msg.delete()
    except:
        pass


    files, offset, total_results = await get_search_results(
        chat_id,
        movie,
        offset=0,
        filter=True
    )

    # 🔥 SMART FILTER REBUILD (Suggestion Click Case)
    if SMART_SELECTION_MODE:

        smart_languages = set()
        smart_seasons = set()
        smart_qualities = set()
        smart_combined = []

        files = files or []
        all_files = list(files)
        if not files:
            return

        next_offset = offset

        while next_offset:
            more_files, next_offset, _ = await get_search_results(
                chat_id,
                movie,
                offset=next_offset,
                filter=True
            )

            if not more_files:
                break

            all_files.extend(more_files)

        for file in all_files:
            name = (file.file_name or "").lower()
            caption = (file.caption or "").lower()
            text = f"{name} {caption}"

            # language detect
            for lang_key, data in SMART_LANG_MAP.items():
                if any(alias in text for alias in data["aliases"]):
                    smart_languages.add(lang_key)

            # season detect
            for pattern in SMART_SEASON_REGEX:
                match = re.search(pattern, text)
                if match:
                    num = re.search(r"\d{1,2}", match.group())
                    if num:
                        smart_seasons.add(f"S{int(num.group()):02d}")
                    break

            # quality detect
            q = re.search(SMART_QUALITY_REGEX, text)
            if q:
                smart_qualities.add(q.group())

            # 🔥 combined detect
            has_season = any(re.search(pattern, text) for pattern in SMART_SEASON_REGEX)

            episode_range = re.search(
                r'(s\d{1,2}\s*-\s*s?\d{1,2})|(e\d{1,2}\s*-\s*e?\d{1,2})|(episode\s*\d{1,2}\s*-\s*\d{1,2})',
                text
			)

            has_keyword = any(x in text for x in [
                "complete", "season complete", "complete bengali series",
                "complete hindi series", "complete bangladeshi series",
                "complete bangladesi series", "full bangla series",
                "complete english series", "full bengali series",
                "full hindi series", "complete season", "all episodes",
                "batch", "combined", "season pack",
                "complete series", "full series"
            ])
            if ((has_season and has_keyword) or episode_range) and file not in smart_combined:
                smart_combined.append(file)
	
        key = f"{chat_id}-{user_msg.id}"

        temp.GETALL[key] = all_files
        temp.SMART_FILTERS[key] = {
            "languages": sorted(smart_languages),
            "seasons": sorted(smart_seasons),
            "qualities": sorted(smart_qualities),
            "combined": smart_combined
	    }

    if files:
        if not user_msg:
            return await query.answer("Request expired ❌", show_alert=True)

        k = (movie, files, offset, total_results)
        await auto_filter(bot, user_msg, k)

    else:
        reqstr1 = query.from_user.id if query.from_user else 0
        reqstr = await bot.get_users(reqstr1)

        if NO_RESULTS_MSG:
            await bot.send_message(
                chat_id=BIN_CHANNEL,
                text=script.NORSLTS.format(reqstr.id, reqstr.mention, movie)
            )

        # ❗ এখানে edit না করে নতুন message send করাই safe
        contact_admin_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                "ᴄʟɪᴄᴋ ᴛᴏ ʀᴇǫᴜᴇsᴛ",
                url=SUPPORT_GRP
            )]]
        )

        msg = await bot.send_message(
            chat_id=chat_id,
            text=f"sᴏʀʀʏ {query.from_user.mention},\n\n{script.MVE_NT_FND}",
            reply_markup=contact_admin_button
	    )

        await asyncio.sleep(10)
        await msg.delete()
                
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    lazyData = query.data
    try:
        link = await client.create_chat_invite_link(int(REQST_CHANNEL))
    except:
        pass
    if query.data == "close_data":
        await query.message.delete()     
        
    if query.data.startswith("file"):
        parts = query.data.split("#")
        file_id = parts[1]
        user = None
        if query.message.reply_to_message and query.message.reply_to_message.from_user:
            user = query.message.reply_to_message.from_user.id
        if user and query.from_user.id != int(user):
            await query.answer(
                script.ALRT_TXT.format(query.from_user.first_name),
                show_alert=True
            )
            return
        chat_id = query.message.chat.id if query.message else query.from_user.id

        await query.answer(
            url=f"https://t.me/{temp.U_NAME}?start=file_{chat_id}_{file_id}"
        )
		
    elif query.data.startswith("sendfiles"):
        clicked = query.from_user.id
        ident, key = query.data.split("#") 
        settings = await get_settings(query.message.chat.id)
        try:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=allfiles_{query.message.chat.id}_{key}")
            return
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles3_{key}")
        except Exception as e:
            LOGGER.exception("Error in delete callback")
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles4_{key}")
            
    elif query.data.startswith("del"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        settings = await get_settings(query.message.chat.id)
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                LOGGER.error(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")

    elif query.data == "pages":
        await query.answer()    
    
    elif query.data.startswith("killfilesdq"):
        _, keyword = query.data.split("#")

        if query.from_user.id not in ADMINS:
            return await query.answer("❌ Not allowed", show_alert=True)

        await query.answer("⏳ Processing...", show_alert=False)
        try:
            await query.message.edit_text(
                f"<b>Fetching files for: <code>{keyword}</code></b>"
            )
        except MessageNotModified:
            pass

        files, total = await get_bad_files(keyword)

        if not files:
            try:
                return await query.message.edit_text("<b>No files found.</b>")
            except MessageNotModified:
                return

        try:
            await query.message.edit_text(
                f"<b>Found {len(files)} files.\nDeleting in 3 seconds...</b>"
            )
        except MessageNotModified:
            pass

        await asyncio.sleep(3)

        try:
            file_ids = [file.file_id for file in files]

            result1 = await Media.collection.delete_many({"_id": {"$in": file_ids}})
            deleted = result1.deleted_count if result1 else 0

            if MULTIPLE_DB:
                result2 = await Media2.collection.delete_many({"_id": {"$in": file_ids}})
                deleted += result2.deleted_count if result2 else 0

            LOGGER.info(f"Deleted {deleted} files for keyword: {keyword}")

            try:
                await query.message.edit_text(
                    f"<b>✅ Successfully deleted {deleted} files\nfor query: <code>{keyword}</code></b>"
                )
            except MessageNotModified:
                pass

        except Exception as e:
            LOGGER.exception("Error in killfilesdq")
            try:
                await query.message.edit_text(
                    "<b>❌ Error occurred while deleting files.</b>"
                )
            except MessageNotModified:
                pass 

    elif query.data.startswith("show_option"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"unavailable#{from_user}"),
                InlineKeyboardButton("• ᴜᴘʟᴏᴀᴅᴇᴅ •", callback_data=f"uploaded#{from_user}")
             ],[
                InlineKeyboardButton("• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"already_available#{from_user}")
             ],[
                InlineKeyboardButton("• ɴᴏᴛ ʀᴇʟᴇᴀꜱᴇᴅ •", callback_data=f"Not_Released#{from_user}"),
                InlineKeyboardButton("• Type Correct Spelling •", callback_data=f"Type_Correct_Spelling#{from_user}")
             ],[
                InlineKeyboardButton("• Not Available In The Hindi •", callback_data=f"Not_Available_In_The_Hindi#{from_user}")
             ]]
        btn2 = [[
                 InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Hᴇʀᴇ ᴀʀᴇ ᴛʜᴇ ᴏᴘᴛɪᴏɴs !")
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
        
    elif query.data.startswith("unavailable"):
        ident, from_user = query.data.split("#")
        btn = [
            [InlineKeyboardButton("• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"unalert#{from_user}")]
        ]
        btn2 = [
            [InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=link.invite_link),
            InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")]
        ]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uɴᴀᴠᴀɪʟᴀʙʟᴇ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=f"<b>Hᴇʏ {user.mention},</b>\n\n<u>{content}</u> Hᴀs Bᴇᴇɴ Mᴀʀᴋᴇᴅ Aᴅ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ...💔\n\n#Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️",
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=f"<b>Hᴇʏ {user.mention},</b>\n\n<u>{content}</u> Hᴀs Bᴇᴇɴ Mᴀʀᴋᴇᴅ Aᴅ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ...💔\n\n#Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️\n\n<small>Bʟᴏᴄᴋᴇᴅ? Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ᴍᴇꜱꜱᴀɢᴇꜱ.</small></b>",
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
   
    elif query.data.startswith("Not_Released"):
        ident, from_user = query.data.split("#")
        btn = [[InlineKeyboardButton("📌 Not Released 📌", callback_data=f"nralert#{from_user}")]]
        btn2 = [[
            InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=link.invite_link),
            InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")
        ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Nᴏᴛ Rᴇʟᴇᴀꜱᴇᴅ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>Hᴇʏ {user.mention}\n\n"
                        f"<code>{content}</code>, ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ɴᴏᴛ ʙᴇᴇɴ ʀᴇʟᴇᴀꜱᴇᴅ ʏᴇᴛ\n\n"
                        f"#CᴏᴍɪɴɢSᴏᴏɴ...🕊️✌️</b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>Hᴇʏ {user.mention}</u>\n\n"
                        f"<b><code>{content}</code>, ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ɴᴏᴛ ʙᴇᴇɴ ʀᴇʟᴇᴀꜱᴇᴅ ʏᴇᴛ\n\n"
                        f"#CᴏᴍɪɴɢSᴏᴏɴ...🕊️✌️\n\n"
                        f"<small>Bʟᴏᴄᴋᴇᴅ? Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ᴍᴇꜱꜱᴀɢᴇꜱ.</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("Type_Correct_Spelling"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("♨️ Type Correct Spelling ♨️", callback_data=f"wsalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=link.invite_link),
                 InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Cᴏʀʀᴇᴄᴛ Sᴘᴇʟʟɪɴɢ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>Hᴇʏ {user.mention}\n\n"
                        f"Wᴇ Dᴇᴄʟɪɴᴇᴅ Yᴏᴜʀ Rᴇǫᴜᴇsᴛ <code>{content}</code>, Bᴇᴄᴀᴜsᴇ Yᴏᴜʀ Sᴘᴇʟʟɪɴɢ Wᴀs Wʀᴏɴɢ 😢\n\n"
                        f"#Wʀᴏɴɢ_Sᴘᴇʟʟɪɴɢ 😑</b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>Hᴇʏ {user.mention}</u>\n\n"
                        f"<b><code>{content}</code>, Bᴇᴄᴀᴜsᴇ Yᴏᴜʀ Sᴘᴇʟʟɪɴɢ Wᴀs Wʀᴏɴɢ 😢\n\n"
                        f"#Wʀᴏɴɢ_Sᴘᴇʟʟɪɴɢ 😑\n\n"
                        f"<small>Bʟᴏᴄᴋᴇᴅ? Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ᴍᴇꜱꜱᴀɢᴇꜱ.</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("Not_Available_In_The_Hindi"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton(" Not Available In The Hindi ", callback_data=f"hnalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=link.invite_link),
                 InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ Iɴ Hɪɴᴅɪ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>Hᴇʏ {user.mention}\n\n"
                        f"Yᴏᴜʀ Rᴇǫᴜᴇsᴛ <code>{content}</code> ɪs Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ʀɪɢʜᴛ ɴᴏᴡ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ\n\n"
                        f"#Hɪɴᴅɪ_ɴᴏᴛ_ᴀᴠᴀɪʟᴀʙʟᴇ ❌</b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>Hᴇʏ {user.mention}</u>\n\n"
                        f"<b><code>{content}</code> ɪs Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ʀɪɢʜᴛ ɴᴏᴡ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ\n\n"
                        f"#Hɪɴᴅɪ_ɴᴏᴛ_ᴀᴠᴀɪʟᴀʙʟᴇ ❌\n\n"
                        f"<small>Bʟᴏᴄᴋᴇᴅ? Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ᴍᴇꜱꜱᴀɢᴇꜱ.</small></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("uploaded"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴜᴘʟᴏᴀᴅᴇᴅ •", callback_data=f"upalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=link.invite_link),
                 InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("🔍 ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ 🔎", url=GRP_LNK)
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uᴘʟᴏᴀᴅᴇᴅ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>Hᴇʏ {user.mention},\n\n"
                        f"<u>{content}</u> Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ʙᴇᴇɴ ᴜᴘʟᴏᴀᴅᴇᴅ ʙʏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs.\n"
                        f"Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>\n\n"
                        f"#Uᴘʟᴏᴀᴅᴇᴅ✅"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<u>{content}</u>\n\n"
                        f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ʙᴇᴇɴ ᴜᴘʟᴏᴀᴅᴇᴅ ʙʏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs."
                        f"Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>\n\n"
                        f"#Uᴘʟᴏᴀᴅᴇᴅ✅\n\n"
                        f"<small>Bʟᴏᴄᴋᴇᴅ? Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ᴍᴇꜱꜱᴀɢᴇꜱ.</small>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("already_available"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"alalert#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=link.invite_link),
                 InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("🔍 ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ 🔎", url=GRP_LNK)
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b><strike>{content}</strike></b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ !")
            content = extract_request_content(query.message.text)
            try:
                await client.send_message(
                    chat_id=int(from_user),
                    text=(
                        f"<b>Hᴇʏ {user.mention},\n\n"
                        f"<u>{content}</u> Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ɪɴ ᴏᴜʀ ʙᴏᴛ'ꜱ ᴅᴀᴛᴀʙᴀꜱᴇ.\n"
                        f"Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>\n\n"
                        f"#Aᴠᴀɪʟᴀʙʟᴇ 💗"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
            except UserIsBlocked:
                await client.send_message(
                    chat_id=int(SUPPORT_CHAT_ID),
                    text=(
                        f"<b>Hᴇʏ {user.mention},\n\n"
                        f"<u>{content}</u> Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ɪɴ ᴏᴜʀ ʙᴏᴛ'ꜱ ᴅᴀᴛᴀʙᴀꜱᴇ.\n"
                        f"Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>\n\n"
                        f"#Aᴠᴀɪʟᴀʙʟᴇ 💗\n"
                        f"<small>Bʟᴏᴄᴋᴇᴅ? Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ᴍᴇꜱꜱᴀɢᴇꜱ.</small></i>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn2)
                )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
            
    
    elif query.data.startswith("alalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"Hᴇʏ {user.first_name}, Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ ✅",
                show_alert=True
            )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴇɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs ❌", show_alert=True)

    elif query.data.startswith("upalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"Hᴇʏ {user.first_name}, Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ Uᴘʟᴏᴀᴅᴇᴅ 🔼",
                show_alert=True
            )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴇɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs ❌", show_alert=True)

    elif query.data.startswith("unalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"Hᴇʏ {user.first_name}, Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️",
                show_alert=True
            )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴇɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs ❌", show_alert=True)

    elif query.data.startswith("hnalert"):
        ident, from_user = query.data.split("#")  # Hindi Not Available
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"Hᴇʏ {user.first_name}, Tʜɪꜱ ɪꜱ Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ❌",
                show_alert=True
            )
        else:
            await query.answer("Nᴏᴛ ᴀʟʟᴏᴡᴇᴅ — ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴛʜᴇ ʀᴇǫᴜᴇꜱᴛᴇʀ ❌", show_alert=True)

    elif query.data.startswith("nralert"):
        ident, from_user = query.data.split("#")  # Not Released
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"Hᴇʏ {user.first_name}, Tʜᴇ Mᴏᴠɪᴇ/ꜱʜᴏᴡ ɪꜱ Nᴏᴛ Rᴇʟᴇᴀꜱᴇᴅ Yᴇᴛ 🆕",
                show_alert=True
            )
        else:
            await query.answer("Yᴏᴜ ᴄᴀɴ'ᴛ ᴅᴏ ᴛʜɪꜱ ᴀꜱ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴛʜᴇ ᴏʀɪɢɪɴᴀʟ ʀᴇǫᴜᴇꜱᴛᴇʀ ❌", show_alert=True)

    elif query.data.startswith("wsalert"):
        ident, from_user = query.data.split("#")  # Wrong Spelling
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(
                f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇǫᴜᴇꜱᴛ ᴡᴀꜱ ʀᴇᴊᴇᴄᴛᴇᴅ ᴅᴜᴇ ᴛᴏ ᴡʀᴏɴɢ sᴘᴇʟʟɪɴɢ ❗",
                show_alert=True
            )
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ sᴇᴇ ᴛʜɪꜱ ❌", show_alert=True)

    
    elif lazyData.startswith("streamfile"):
        _, file_id = lazyData.split(":")
        try:
            user_id = query.from_user.id
            is_premium_user = await db.has_premium_access(user_id)
            if PAID_STREAM and not is_premium_user:
                premiumbtn = [[InlineKeyboardButton("𝖡𝗎𝗒 𝖯𝗋𝖾𝗆𝗂𝗎𝗆 ♻️", callback_data='buy')]]
                await query.answer("<b>📌 ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ᴏɴʟʏ ꜰᴏʀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ</b>", show_alert=True)
                await query.message.reply("<b>📌 ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ɪꜱ ᴏɴʟʏ ꜰᴏʀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ. ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ ᴛᴏ ᴀᴄᴄᴇꜱꜱ ᴛʜɪꜱ ꜰᴇᴀᴛᴜʀᴇ ✅</b>", reply_markup=InlineKeyboardMarkup(premiumbtn))
                return
            username =  query.from_user.mention 
            silent_msg = await client.send_cached_media(
                chat_id=BIN_CHANNEL,
                file_id=file_id,
            )
            fileName = {quote_plus(get_name(silent_msg))}
            silent_stream = f"{URL}watch/{str(silent_msg.id)}/{quote_plus(get_name(silent_msg))}?hash={get_hash(silent_msg)}"
            silent_download = f"{URL}{str(silent_msg.id)}/{quote_plus(get_name(silent_msg))}?hash={get_hash(silent_msg)}"
            btn= [[
                InlineKeyboardButton("𝖲𝗍𝗋𝖾𝖺𝗆", url=silent_stream),
                InlineKeyboardButton("𝖣𝗈𝗐𝗇𝗅𝗈𝖺𝖽", url=silent_download)        
	    ]]
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
	    )
            await silent_msg.reply_text(
                text=f"•• ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n•• ᖴᎥᒪᗴ Nᗩᗰᗴ : {fileName}",
                quote=True,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(btn)
	    )                
        except Exception as e:
            LOGGER.error(e)
            await query.answer(f"⚠️ SOMETHING WENT WRONG \n\n{e}", show_alert=True)
            return
           
    
    elif query.data == "pagesn1":
        await query.answer(text=script.PAGE_TXT, show_alert=True)

    elif query.data == "start":
        await query.answer()
        buttons = get_main_buttons()

        current_time = datetime.now(pytz.timezone(TIMEZONE))
        hour = current_time.hour

        if hour < 12:
            gtxt = "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ"
        elif hour < 17:
            gtxt = "ɢᴏᴏᴅ ᴀғᴛᴇʀɴᴏᴏɴ"
        elif hour < 21:
            gtxt = "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ"
        else:
            gtxt = "ɢᴏᴏᴅ ɴɪɢʜᴛ"

        try:
            await query.edit_message_media(
                InputMediaPhoto(
                    media=random.choice(PICS),
                    caption=script.START_TXT.format(
                        user=query.from_user.mention,
                        greet=gtxt
                    ),
                    parse_mode=enums.ParseMode.HTML
                )
            )
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except:
            await query.edit_message_text(
                text=script.START_TXT.format(
                    user=query.from_user.mention,
                    greet=gtxt
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
			)
  
    elif query.data == "give_trial":
        try:
            user_id = query.from_user.id
            has_free_trial = await db.check_trial_status(user_id)
            if has_free_trial:
                await query.answer("🚸 ʏᴏᴜ'ᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ ʏᴏᴜʀ ꜰʀᴇᴇ ᴛʀɪᴀʟ ᴏɴᴄᴇ !\n\n📌 ᴄʜᴇᴄᴋᴏᴜᴛ ᴏᴜʀ ᴘʟᴀɴꜱ ʙʏ : /plan", show_alert=True)
                return
            else:            
                await db.give_free_trial(user_id)
                await query.message.reply_text(
                    text="<b>🥳 ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴꜱ\n\n🎉 ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ꜰʀᴇᴇ ᴛʀᴀɪʟ ꜰᴏʀ <u>5 ᴍɪɴᴜᴛᴇs</u> ꜰʀᴏᴍ ɴᴏᴡ !</b>",
                    quote=False,
                    disable_web_page_preview=True,                  
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💸 ᴄʜᴇᴄᴋᴏᴜᴛ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴꜱ 💸", callback_data='seeplans')]]))
                return    
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "free":
        await query.answer()
        buttons = [[
            InlineKeyboardButton('⚜️ ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ɢᴇᴛ ꜰʀᴇᴇ ᴛʀɪᴀʟ', callback_data="give_trial")
        ],[
            InlineKeyboardButton('⋞ ʙᴀᴄᴋ', callback_data='other'),
            InlineKeyboardButton('7 / 7', callback_data='pagesn1'),
            InlineKeyboardButton('ɴᴇxᴛ ⋟', callback_data='bronze')
        ],[
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ⇋', callback_data='premium')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.FREE_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "premium":
        await query.answer()

        buttons = [
            [
                InlineKeyboardButton("Rᴇғғᴇʀ Tᴏ Gᴇᴛ Pʀᴇᴍɪᴜᴍ", callback_data="reffff")
            ],
            [
                InlineKeyboardButton("Bʀᴏɴᴢᴇ", callback_data="bronze"),
                InlineKeyboardButton("Sɪʟᴠᴇʀ", callback_data="silver")
            ],
            [
                InlineKeyboardButton("Gᴏʟᴅ", callback_data="gold"),
                InlineKeyboardButton("Pʟᴀᴛɪɴᴜᴍ", callback_data="platinum")
            ],
            [
                InlineKeyboardButton("Dɪᴀᴍᴏɴᴅ", callback_data="diamond"),
                InlineKeyboardButton("Oᴛʜᴇʀ", callback_data="other")
            ],
            [
                InlineKeyboardButton("Gᴇᴛ A Free Tʀɪᴀʟ Fᴏʀ 5 Mɪɴᴜᴛᴇs 🫣", callback_data="free")
            ],
            [
                InlineKeyboardButton("⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋", callback_data="home")
            ]
        ]

        await query.message.edit_media(
            InputMediaPhoto(
                media=random.choice(PICS),
                caption=script.BPREMIUM_TXT,
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif query.data == "bronze":
        await query.answer()

        buttons = [
            [
                InlineKeyboardButton("🔐 Click here to buy premium", callback_data="buy")
            ],
            [
                InlineKeyboardButton("⋞ Back", callback_data="free"),
                InlineKeyboardButton("1 / 7", callback_data="pagesn1"),
                InlineKeyboardButton("Next ⋟", callback_data="silver")
            ],
            [
                InlineKeyboardButton("⇋ Back ⇋", callback_data="premium")
            ]
        ]

        await query.message.edit_media(
            InputMediaPhoto(
                media="https://graph.org/file/670f6df9f755dc2c9a00a.jpg",
                caption=script.BRONZE_TXT.format(query.from_user.mention),
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif query.data == "silver":
        await query.answer()

        buttons = [
            [
                InlineKeyboardButton("🔐 Click here to buy premium", callback_data="buy")
            ],
            [
                InlineKeyboardButton("⋞ Back", callback_data="bronze"),
                InlineKeyboardButton("2 / 7", callback_data="pagesn1"),
                InlineKeyboardButton("Next ⋟", callback_data="gold")
            ],
            [
                InlineKeyboardButton("⇋ Back ⇋", callback_data="premium")
            ]
        ]

        await query.message.edit_media(
            InputMediaPhoto(
                media="https://graph.org/file/670f6df9f755dc2c9a00a.jpg",
                caption=script.SILVER_TXT.format(query.from_user.mention),
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif query.data == "gold":
        await query.answer()

        buttons = [
            [
                InlineKeyboardButton("🔐 Click here to buy premium", callback_data="buy")
            ],
            [
                InlineKeyboardButton("⋞ Back", callback_data="silver"),
                InlineKeyboardButton("3 / 7", callback_data="pagesn1"),
                InlineKeyboardButton("Next ⋟", callback_data="platinum")
            ],
            [
                InlineKeyboardButton("⇋ Back ⇋", callback_data="premium")
            ]
        ]

        await query.message.edit_media(
            InputMediaPhoto(
                media="https://graph.org/file/670f6df9f755dc2c9a00a.jpg",
                caption=script.GOLD_TXT.format(query.from_user.mention),
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif query.data == "platinum":
        await query.answer()

        buttons = [
            [
                InlineKeyboardButton(
                    "🔐 Click here to buy premium",
                    callback_data="buy"
                )
            ],
            [
                InlineKeyboardButton(
                    "⋞ Back",
                    callback_data="gold"
                ),
                InlineKeyboardButton(
                    "4 / 7",
                    callback_data="pagesn1"
                ),
                InlineKeyboardButton(
                    "Next ⋟",
                    callback_data="diamond"
                )
            ],
            [
                InlineKeyboardButton(
                    "⇋ Back ⇋",
                    callback_data="premium"
                )
            ]
        ]

        await query.message.edit_media(
            InputMediaPhoto(
                media="https://graph.org/file/670f6df9f755dc2c9a00a.jpg",
                caption=script.PLATINUM_TXT.format(
                    query.from_user.mention
                ),
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif query.data == "diamond":
        await query.answer()

        buttons = [
            [
                InlineKeyboardButton("🔐 Click here to buy premium", callback_data="buy")
            ],
            [
                InlineKeyboardButton("⋞ Back", callback_data="platinum"),
                InlineKeyboardButton("5 / 7", callback_data="pagesn1"),
                InlineKeyboardButton("Next ⋟", callback_data="other")
            ],
            [
                InlineKeyboardButton("⇋ Back ⇋", callback_data="premium")
            ]
        ]

        await query.message.edit_media(
            InputMediaPhoto(
                media="https://graph.org/file/670f6df9f755dc2c9a00a.jpg",
                caption=script.DIAMOND_TXT.format(query.from_user.mention),
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
	    )

    elif query.data == "other":
        await query.answer()

        buttons = [
            [
                InlineKeyboardButton("☎️ Contact Owner", url=OWNER_LNK)
            ],
            [
                InlineKeyboardButton("⋞ Back", callback_data="diamond"),
                InlineKeyboardButton("6 / 7", callback_data="pagesn1"),
                InlineKeyboardButton("Next ⋟", callback_data="free")
            ],
            [
                InlineKeyboardButton("⇋ Back ⇋", callback_data="premium")
            ]
        ]

        await query.message.edit_media(
            InputMediaPhoto(
                media="https://graph.org/file/670f6df9f755dc2c9a00a.jpg",
                caption=script.OTHER_TXT.format(query.from_user.mention),
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    elif query.data == "buy":
        try:
            btn = [[InlineKeyboardButton('🌟 ᴘᴀʏ ᴠɪᴀ ᴛᴇʟᴇɢʀᴀᴍ sᴛᴀʀ 🌟', callback_data='star')],[InlineKeyboardButton('💸 ᴘᴀʏ ᴠɪᴀ ᴜᴘɪ/ǫʀ ᴄᴏᴅᴇ 💸', callback_data='upi')],[InlineKeyboardButton('⋞ ʙᴀᴄᴋ', callback_data='premium')]]
            reply_markup = InlineKeyboardMarkup(btn)
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(SUBSCRIPTION)
	        ) 
            await query.message.edit_text(
                text=script.PREMIUM_TEXT.format(query.from_user.mention),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            ) 
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "upi":
        try:
            btn = [[ 
                InlineKeyboardButton('📱 ꜱᴇɴᴅ  ᴘᴀʏᴍᴇɴᴛ ꜱᴄʀᴇᴇɴꜱʜᴏᴛ', url=OWNER_LNK),
            ],[
                InlineKeyboardButton('⋞ ʙᴀᴄᴋ', callback_data='buy')
            ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(SUBSCRIPTION)
	        ) 
            await query.message.edit_text(
                text=script.PREMIUM_UPI_TEXT.format(query.from_user.mention),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            ) 
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "star":
        try:
            btn = [
                InlineKeyboardButton(f"{stars}⭐", callback_data=f"buy_{stars}")
                for stars, days in STAR_PREMIUM_PLANS.items()
            ]
            buttons = [btn[i:i + 2] for i in range(0, len(btn), 2)]
            buttons.append([InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data="buy")])
            reply_markup = InlineKeyboardMarkup(buttons)
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(PICS))
	        ) 
            await query.message.edit_text(
                text=script.PREMIUM_STAR_TEXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
	    )
        except Exception as e:
            LOGGER.error(e)

    elif query.data == "earn":
        try:
            btn = [[ 
                InlineKeyboardButton('⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋', callback_data='start')
            ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_text(
                text=script.EARN_INFO.format(temp.B_LINK),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            ) 
        except Exception as e:
            LOGGER.error(e)
                    
    elif query.data == "me":
        buttons = [[
            InlineKeyboardButton ('❤️‍🔥 Sᴏᴜʀᴄᴇ', callback_data='source'),
        ],[
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋', callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.U_NAME, temp.B_NAME, OWNER_LNK),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        
    elif query.data == "source":
        buttons = [[
            InlineKeyboardButton('☠︎︎ Sᴏᴜʀᴄᴇ Cᴏᴅᴇ ☠︎︎', url='https://t.me/Graduate_Movies'),
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ⇋', callback_data='me')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.SOURCE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "ref_point":
        await query.answer(f'You Have: {referdb.get_refer_points(query.from_user.id)} Refferal points.', show_alert=True)
    
    
    elif query.data == "disclaimer":
            btn = [[
                    InlineKeyboardButton("⇋ ʙᴀᴄᴋ ⇋", callback_data="start")
                  ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_text(
                text=(script.DISCLAIMER_TXT),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML 
            )
			
        
async def auto_filter(client, msg, spoll=False):
    chat_id = msg.chat.id
    settings = await get_settings(chat_id)

    cap = ""
    message = msg

    original_query = None
    fallback_query = None
    fallback_info = None

    if isinstance(spoll, tuple):
        search = spoll[0]
        files = spoll[1]
        offset = spoll[2]
        total_results = spoll[3]
    else:
        search = None
        files = []
        offset = 0
        total_results = 0

    if not message or not isinstance(getattr(message, "text", None), str):
        return
    key = f"{message.chat.id}-{message.reply_to_message.id if message.reply_to_message else message.id}"

    # reset multi select session
    temp.MULTI_SELECT.pop(key, None)
    temp.MULTI_FILES.pop(key, None)

    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    # ================= SMART MODE INIT =================
    if SMART_SELECTION_MODE:
        if not hasattr(temp, "SMART_FILTERS"):
            temp.SMART_FILTERS = {}
    # ==================================================
    if not isinstance(spoll, tuple):
        if message.text.startswith("/"): return
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if len(message.text) < 100:
            if not search:
                search = await replace_words(message.text)		
            search = search.lower()
            search = search.replace("-", " ")
            search = search.replace(":","")
            search = search.replace("'","")
            search = re.sub(r'[^a-zA-Z0-9\s]', '', search)
            search = re.sub(r'\s+', ' ', search).strip()
            if not re.search(r'[a-zA-Z0-9]', search): #ignore non english request 
                return
            if not is_meaningful_query(search):
                return
            m=await message.reply_text(f'<b><i>ᴡᴀɪᴛ {message.from_user.mention}, sᴇᴀʀᴄʜɪɴɢ ʏᴏᴜʀ ǫᴜᴇʀʏ: <i>{search}...</i></b>', reply_to_message_id=message.id)
            
            if isinstance(spoll, tuple):
                files, offset, total_results = spoll[1], spoll[2], spoll[3]
            else:
                files, offset, total_results = await get_search_results(
                    message.chat.id,
                    search,
                    offset=0,
                    filter=True
	            )
            files = files or []
            # 🔥 APOSTROPHE FALLBACK (second search only if first fails)
            # 🔥 ADVANCED SYMBOL NORMALIZATION FALLBACK
            if not files and re.search(r"[\'\:\.,/]", message.text):

                raw = message.text.lower()

                # Variant 1 → remove symbols completely
                variant1 = re.sub(r"[\'\:\.,/]", "", raw)

                # Variant 2 → replace symbols with space
                variant2 = re.sub(r"[\'\:\.,/]", " ", raw)

                variants = []

                for v in [variant1, variant2]:

                    v = v.replace("-", " ")
                    v = re.sub(r'[^a-zA-Z0-9\s]', '', v)
                    v = re.sub(r'\s+', ' ', v).strip()

                    if v and v != search:
                        variants.append(v)

                for v in variants:
                    files, offset, total_results = await get_search_results(
                       message.chat.id,
                        v,
                        offset=0,
                        filter=True
                    )

                    if files:
                        search = v
                        break

                #fallback_search = message.text.lower()
                #fallback_search = fallback_search.replace("-", " ")
                #fallback_search = fallback_search.replace(":", "")
                #fallback_search = fallback_search.replace("'", " ")
                #fallback_search = re.sub(r'[^a-zA-Z0-9\s]', '', fallback_search)
                #fallback_search = re.sub(r'\s+', ' ', fallback_search).strip()

                #if fallback_search and fallback_search != search:
                    #files, offset, total_results = await get_search_results(
                        #message.chat.id,
                        #fallback_search,
                        #offset=0,
                        #filter=True
		            #)
            # ===================================
            # PREMIUM SMART FALLBACK ENGINE
            # ===================================

            fallback_info = None
            original_query = search
            fallback_query = None

            if not files:

                is_series_request = bool(
                    re.search(r"s\d{1,2}\s*e\d{1,3}", search, re.IGNORECASE) or
                    re.search(r"s\d{1,2}e\d{1,3}", search, re.IGNORECASE) or
                    re.search(r"s\d{1,2}", search, re.IGNORECASE) or
                    re.search(r"season\s*\d{1,2}", search, re.IGNORECASE) or
                    re.search(r"\b\d{1,2}\b$", search)
				)

                has_year = bool(re.search(r"\b(19|20)\d{2}\b", search))

                # 1️⃣ Episode → Season
                if is_series_request:
                    season_only = re.sub(
                        r"(s\d{1,2}\s*e\d{1,3}|s\d{1,2}e\d{1,3}|e\d{1,3})",
                        lambda m: re.search(r"s\d{1,2}", m.group(0), re.IGNORECASE).group(0)
                        if re.search(r"s\d{1,2}", m.group(0), re.IGNORECASE)
                        else "",
                        search,
                        flags=re.IGNORECASE
                    ).strip()
                    if season_only != search:
                        files, offset, total_results = await get_search_results(
                            message.chat.id, season_only, offset=0, filter=True
                        )

                        if files:
                            fallback_query = season_only
                            original_query = season_only
                            search = season_only
                            fallback_info = "ᴇᴘɪsᴏᴅᴇ ɴᴏᴛ ғᴏᴜɴᴅ. sʜᴏᴡɪɴɢ ᴀʟʟ sᴇᴀsᴏɴs."

                # 2️⃣ Season → Title
                if not files and is_series_request:
                    title_only = re.sub(
                        r"(s\d{1,2}\s*e\d{1,3}|s\d{1,2}e\d{1,3}|s\d{1,2}|season\s*\d{1,2}|\b\d{1,2}\b)",
                        "",
                        search,
                        flags=re.IGNORECASE
                    ).strip()

                    title_only = re.sub(r"\s+", " ", title_only).strip()

                    if title_only and title_only != search:
                        files, offset, total_results = await get_search_results(
                            message.chat.id, title_only, offset=0, filter=True
                        )

                        if files:
                            fallback_query = title_only
                            original_query = title_only
                            search = title_only
                            fallback_info = "ʀᴇǫᴜᴇsᴛᴇᴅ sᴇᴀsᴏɴ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ. sʜᴏᴡɪɴɢ ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ʀᴇsᴜʟᴛs."

                # 3️⃣ Wrong Year fallback
                if not files and has_year:
                    title_without_year = re.sub(
                        r"\b(19|20)\d{2}\b",
                        "",
                        search
                    ).strip()

                    if title_without_year and title_without_year != search:
                        files, offset, total_results = await get_search_results(
                            message.chat.id, title_without_year, offset=0, filter=True
                        )

                        if files:
                            fallback_query = title_without_year
                            original_query = title_without_year   # 🔥 ADD THIS
                            search = title_without_year       
                            fallback_info = f"ɴᴏ ʀᴇsᴜʟᴛs ғᴏʀ ᴛʜᴀᴛ ʏᴇᴀʀ. sʜᴏᴡɪɴɢ ʀᴇsᴜʟᴛs ғᴏʀ '{title_without_year}'."
            uid = message.from_user.id if message.from_user else 0
            key = f"{message.chat.id}-{message.id}"
            if not hasattr(temp, "OWNER"):
                temp.OWNER = {}
            temp.OWNER[key] = uid
            settings = await get_settings(message.chat.id)

            if not hasattr(temp, "PAGE_STATE"):
                temp.PAGE_STATE = {}

            per_page = 10 if settings.get("max_btn") else int(MAX_B_TN)

            # ✅ MAIN STATE (never change, original search)
            if not hasattr(temp, "MAIN_STATE"):
                temp.MAIN_STATE = {}

            temp.MAIN_STATE[key] = {
                "total_results": total_results,
                "per_page": per_page
            }

            # ✅ CURRENT STATE (can change by filter)
            temp.PAGE_STATE[key] = {
                "total_results": total_results,
                "per_page": per_page,
                "current_offset": 0
            }
            # ================= SMART MODE DETECTION =================
            key = f"{message.chat.id}-{message.reply_to_message.id if message.reply_to_message else message.id}"
            FRESH[key] = search
            # ================= SMART MODE: COLLECT ALL FILES =================
            if SMART_SELECTION_MODE and not isinstance(spoll, tuple):
                smart_languages = set()
                smart_seasons = set()
                smart_qualities = set()
                smart_combined = []

                # 🔹 start with first page files
                files = files or []
                all_files = list(files)

                # 🔹 collect remaining pages

                next_offset = offset

                while next_offset:
                    more_files, next_offset, _ = await get_search_results(
                        message.chat.id,
                        search,
                        offset=next_offset,
                        filter=True
                    )

                    if not more_files:
                        break

                    all_files.extend(more_files)

                # 🔹 analyze ALL files (not only 1st page)
                for file in all_files:
                    name = (file.file_name or "").lower()
                    caption = (file.caption or "").lower()

                    text = f"{name} {caption}"
                    # season detect
                    has_season = any(re.search(pattern, text) for pattern in SMART_SEASON_REGEX)
                    episode_range = re.search(
                        r'(s\d{1,2}\s*-\s*s?\d{1,2})|(e\d{1,2}\s*-\s*e?\d{1,2})|(episode\s*\d{1,2}\s*-\s*\d{1,2})',
                        text
					)

                    has_keyword = any(x in text for x in [
                        "complete", "season complete", "complete bengali series",
                        "complete hindi series", "complete bangladeshi series",
                        "complete bangladesi series", "full bangla series",
                        "complete english series", "full bengali series",
                        "full hindi series", "complete season", "all episodes",
                        "batch", "combined", "season pack",
                        "complete series", "full series"
                    ])
                    # combined detect ONLY if season present
                    if ((has_season and has_keyword) or episode_range) and file not in smart_combined:
                        smart_combined.append(file)

                    # 🔤 Language detection
                    for lang_key, data in SMART_LANG_MAP.items():
                        for alias in data["aliases"]:
                            if re.search(rf"(^|[.\s_-]){alias}([.\s_-]|$)", name):
                                smart_languages.add(lang_key)
                                break

                    # 📺 Season detection
                    for pattern in SMART_SEASON_REGEX:
                        match = re.search(pattern, name)
                        if match:
                            num = re.search(r"\d{1,2}", match.group())
                            if num:
                                smart_seasons.add(f"S{int(num.group()):02d}")
                            break

                    # 🎞 Quality detection
                    q = re.search(SMART_QUALITY_REGEX, name)
                    if q:
                        smart_qualities.add(q.group())


                # 🔹 store EVERYTHING for smart filters
                temp.GETALL[key] = all_files
                temp.SMART_FILTERS[key] = {
                    "languages": sorted(smart_languages),
                    "seasons": sorted(smart_seasons),
                    "qualities": sorted(smart_qualities),
                    "combined": smart_combined
				    }
            # ========================================================
            if not files:
                if settings["spell_check"]:

                    ai_sts = await m.edit('<b>ғɪxɪɴɢ sᴘᴇʟʟɪɴɢ ᴡɪᴛʜ ᴀɪ</b> 🕵️')

                    is_misspelled = await ai_spell_check(
                        chat_id=message.chat.id,
                        wrong_name=search
                    )

                    if is_misspelled:

                        await ai_sts.edit(
                            f"<b>ɪ ғɪxᴇᴅ ᴛʜᴇ sᴘᴇʟʟɪɴɢ → {is_misspelled}</b>\n"
                            f"<b>ɴᴏᴡ sᴇᴀʀᴄʜɪɴɢ...</b>"
                        )

                        await asyncio.sleep(2)
                        await ai_sts.delete()

                        # 🔥 search again with corrected spelling
                        files, offset, total_results = await get_search_results(
                            message.chat.id,
                            is_misspelled,
                            offset=0,
                            filter=True
                        )

                        files = files or []

                        # 🔥 SMART FILTER REBUILD (AI FIX CASE)
                        if SMART_SELECTION_MODE:

                            smart_languages = set()
                            smart_seasons = set()
                            smart_qualities = set()
                            smart_combined = []

                            all_files = list(files)

                            next_offset = offset

                            while next_offset:
                                more_files, next_offset, _ = await get_search_results(
                                    message.chat.id,
                                    is_misspelled,
                                    offset=next_offset,
                                    filter=True
                                )

                                if not more_files:
                                    break

                                all_files.extend(more_files)

                            for file in all_files:
                                name = (file.file_name or "").lower()
                                caption = (file.caption or "").lower()

                                text = f"{name} {caption}"
                                # season detect
                                has_season = any(re.search(pattern, text) for pattern in SMART_SEASON_REGEX)
                                episode_range = re.search(
                                    r'(s\d{1,2}\s*-\s*s?\d{1,2})|(e\d{1,2}\s*-\s*e?\d{1,2})|(episode\s*\d{1,2}\s*-\s*\d{1,2})',
                                    text
								)

                                has_keyword = any(x in text for x in [
                                    "complete", "season complete", "complete bengali series",
                                    "complete hindi series", "complete bangladeshi series",
                                    "complete bangladesi series", "full bangla series",
                                    "complete english series", "full bengali series",
                                    "full hindi series", "complete season", "all episodes",
                                    "batch", "combined", "season pack",
                                    "complete series", "full series"
                                ])
                                # combined detect ONLY if season present
                                if ((has_season and has_keyword) or episode_range) and file not in smart_combined:
                                    smart_combined.append(file)

                                for lang_key, data in SMART_LANG_MAP.items():
                                    for alias in data["aliases"]:
                                        if re.search(rf"(^|[.\s_-]){alias}([.\s_-]|$)", name):
                                            smart_languages.add(lang_key)
                                            break

                                for pattern in SMART_SEASON_REGEX:
                                    match = re.search(pattern, name)
                                    if match:
                                        num = re.search(r"\d{1,2}", match.group())
                                        if num:
                                            smart_seasons.add(f"S{int(num.group()):02d}")
                                        break

                                q = re.search(SMART_QUALITY_REGEX, name)
                                if q:
                                    smart_qualities.add(q.group())

                            temp.GETALL[key] = all_files
                            temp.SMART_FILTERS[key] = {
                                "languages": sorted(smart_languages),
                                "seasons": sorted(smart_seasons),
                                "qualities": sorted(smart_qualities),
                                "combined": smart_combined
	                        }
                        if files:
                            search = is_misspelled
                            FRESH[key] = search
                            original_query = is_misspelled
                            fallback_query = None
                            fallback_info = None
                            
                        else:
                            return await advantage_spell_chok(client, message)

                    else:
                        await ai_sts.delete()
                        return await advantage_spell_chok(client, message)
    else:
        message = msg  # 🔥 FIX: msg is already Message

        search, files, offset, total_results = spoll

        m = await message.reply_text(
            f'<b>ᴡᴀɪᴛ {message.from_user.mention}\nsᴇᴀʀᴄʜɪɴɢ ʏᴏᴜʀ ǫᴜᴇʀʏ :<i>{search}...</i></b>',
            reply_to_message_id=message.id
        )

        settings = await get_settings(message.chat.id)
    #key = f"{message.chat.id}-{message.reply_to_message.id if message.reply_to_message else message.id}"
    FRESH[key] = search
    if SMART_SELECTION_MODE:
        # already stored full result earlier, do nothing
        pass
    else:
        if key not in temp.GETALL:
            temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    if settings.get('button'):
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{silent_size(file.file_size)} ✦ {extract_tag(file.file_name)} {clean_filename(file.file_name)}", callback_data=f'file#{file.file_id}'
                ),
            ]
            for file in files
        ]
        combined_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []

        if not combined_files:
            for f in files:
                name = (f.file_name or "").lower()
                caption = (f.caption or "").lower()
                text = f"{name} {caption}"

                if any(x in text for x in [
                    "complete", "combined", "complete season",
                    "season complete", "all episodes",
                    "season pack", "full bengali series", "complete Bangladeshi series", "bengali series", "Bollywood series", "English series", "Bangladeshi series", "complete series", "full series"
                ]):
                    combined_files.append(f)
                    break
        top_row = [
            InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
            InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0")
        ]

        btn.insert(0, top_row)

        if combined_files:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ᴄᴏᴍʙɪɴᴇᴅ",
                    callback_data=f"fc#{key}#0"
                ),
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])
        else:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])

    else:
        btn = []
        combined_files = temp.SMART_FILTERS.get(key, {}).get("combined") or []

        if not combined_files:
            for f in files:
                name = (f.file_name or "").lower()
                caption = (f.caption or "").lower()
                text = f"{name} {caption}"

                if any(x in text for x in [
                    "complete", "combined", "complete season",
                    "season complete", "all episodes",
                    "season pack", "complete series", "full series", "full bengali series", "complete Bangladeshi series", "bengali series", "Bollywood series", "English series", "Bangladeshi series"
                ]):
                    combined_files.append(f)
                    break
        top_row = [
            InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
            InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
            InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ", callback_data=f"seasons#{key}#0")
        ]

        btn.insert(0, top_row)

        if combined_files:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ᴄᴏᴍʙɪɴᴇᴅ",
                    callback_data=f"fc#{key}#0"
                ),
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
				)
            ])
        else:
            btn.insert(1, [
                InlineKeyboardButton(
                    "ꜱᴇʟᴇᴄᴛ ᴍᴜʟᴛɪ",
                    callback_data=f"ms#{key}#{offset}"
                )
            ])

    if offset != "":
        req = message.from_user.id if message.from_user else 0
        try:
            if settings['max_btn']:
                btn.append(
                    [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⋟",callback_data=f"next_{req}_{key}_{offset}")]
                )
            else:
                btn.append(
                    [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⋟",callback_data=f"next_{req}_{key}_{offset}")]
                )
        except KeyError:
            await save_group_settings(message.chat.id, 'max_btn', True)
            btn.append(
                [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⋟",callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        btn.append(
            [InlineKeyboardButton(text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭",callback_data="pages")]
        )
    imdb = None
    cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
    remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
    DELETE_TIME = settings.get("auto_del_time", AUTO_DELETE_TIME)
    TEMPLATE = script.IMDB_TEMPLATE_TXT    
    poster_url = None
    if imdb:
        poster_url = imdb.get('poster')

        if not poster_url:
            tmdb_data = await fetch_tmdb_data(search, imdb.get('year'))

            if tmdb_data:
                poster_url = await get_best_visual(tmdb_data)
    if not files:
        return
    display_query = fallback_query if fallback_query else original_query

    header_note = ""
    if fallback_info:
        header_note = f"🔎 <i>{fallback_info}</i>\n\n"
    cap = ""
    if imdb:
        cap = header_note + TEMPLATE.format(
            qurey=display_query,
            #qurey=search,
            title=imdb.get("title", "N/A"),
            votes=imdb.get("votes") or imdb.get("vote_count") or "N/A",
            aka=imdb.get("aka", "N/A"),
            seasons=imdb.get("seasons", "N/A"),
            box_office=imdb.get("box_office", "N/A"),
            localized_title=imdb.get("localized_title", "N/A"),
            kind=imdb.get("kind", "N/A"),
            imdb_id=imdb.get("imdb_id", "N/A"),
            cast=imdb.get("cast", "N/A"),
            runtime=imdb.get("runtime", "N/A"),
            countries=imdb.get("countries", "N/A"),
            certificates=imdb.get("certificates", "N/A"),
            languages=imdb.get("languages", "N/A"),
            director=imdb.get("director", "N/A"),
            writer=imdb.get("writer", "N/A"),
            producer=imdb.get("producer", "N/A"),
            composer=imdb.get("composer", "N/A"),
            cinematographer=imdb.get("cinematographer", "N/A"),
            music_team=imdb.get("music_team", "N/A"),
            distributors=imdb.get("distributors", "N/A"),
            release_date=imdb.get("release_date", "N/A"),
            year=imdb.get("year", "N/A"),
            genres=imdb.get("genres", "N/A"),
            poster=poster_url,
            plot=imdb.get("plot", "N/A"),
            rating=imdb.get("rating", "N/A"),
            url=imdb.get("url", "N/A"),
            **locals()
        )

        # ---------------- CAPTION BUILD ----------------
    else:
        if settings.get('button'):
            cap = (
                f"<b><blockquote>Hᴇʏ, {message.from_user.mention}</blockquote>\n"
                f"{header_note}"
                f"ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ - <code>{display_query}</code>\n\n"
                f"🚧 ᴛʜɪꜱ ᴍᴇꜱꜱᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀғᴛᴇʀ ғᴇᴡ ᴍɪɴᴜᴛᴇs.</b>"
            )
        else:
            cap = (
                f"<b><blockquote>Hᴇʏ, {message.from_user.mention}</blockquote>\n"
                f"{header_note}"
                f"ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ - <code>{display_query}</code>\n\n"
                f"🚧 ᴛʜɪꜱ ᴍᴇꜱꜱᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀғᴛᴇʀ ғᴇᴡ ᴍɪɴᴜᴛᴇs.</b>"
            )

            for file_num, file in enumerate(files, start=1):
                cap += (
                    f"<b>{file_num}. "
                    f"<a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>"
                    f"{get_size(file.file_size)} | {clean_filename(file.file_name)}\n\n"
                    f"</a></b>"
                )

        # store AFTER building complete caption
        temp.IMDB_CAP[message.from_user.id] = cap
        #if not settings.get('button'):
            #for file_num, file in enumerate(files, start=1):
                #cap += f"\n\n<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}</a></b>"

                   
    try:
        if imdb and (poster_url or imdb.get("poster")):
            try:
                imdb_poster = imdb.get("poster") if imdb else None
                final_poster = imdb_poster or poster_url
                hehe = await message.reply_photo(
                    photo=final_poster,
                    caption=cap, 
                    reply_markup=InlineKeyboardMarkup(btn), 
                    parse_mode=enums.ParseMode.HTML
                )
                await m.delete()
                if settings['auto_delete']:
                    await asyncio.sleep(DELETE_TIME)
                    await hehe.delete()
                    await message.delete()
            except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                pic = imdb.get('poster')
                if pic:
                    poster = pic.replace('.jpg', "._V1_UX360.jpg")
                    hmm = await message.reply_photo(
                        photo=poster, 
                        caption=cap, 
                        reply_markup=InlineKeyboardMarkup(btn), 
                        parse_mode=enums.ParseMode.HTML
                    )
                    await m.delete()
                    if settings['auto_delete']:
                        await asyncio.sleep(DELETE_TIME)
                        await hmm.delete()
                        await message.delete()
                else:
                    fek = await m.edit_text(
                        text=cap, 
                        reply_markup=InlineKeyboardMarkup(btn), 
                        parse_mode=enums.ParseMode.HTML
                    )
                    if settings['auto_delete']:
                        await asyncio.sleep(DELETE_TIME)
                        await fek.delete()
                        await message.delete()
            except Exception as e:
                LOGGER.error(e)
                fek = await m.edit_text(
                    text=cap, 
                    reply_markup=InlineKeyboardMarkup(btn), 
                    parse_mode=enums.ParseMode.HTML
                )
                if settings['auto_delete']:
                    await asyncio.sleep(DELETE_TIME)
                    await fek.delete()
                    await message.delete()
        else:
            try:
                fuk = await m.edit_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                fuk = await message.reply_text(
                    text=cap,
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
            if settings['auto_delete']:
                await asyncio.sleep(DELETE_TIME)
                try:
                    await fuk.delete()
                except:
                    pass

                try:
                    await message.delete()
                except:
                    pass
    except KeyError:
        await save_group_settings(message.chat.id, 'auto_delete', True)
        pass

def _normalize_query(text: str) -> str:
    text = text.lower().strip()

    # replace separators with space
    text = re.sub(r"[\-_\.]+", " ", text)

    # proloy02 → proloy 02
    text = re.sub(r"(\D)(\d)", r"\1 \2", text)

    # 02 → 2
    text = re.sub(r"\b0+(\d)", r"\1", text)

    # remove special chars
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # collapse spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text

async def ai_spell_check(chat_id, wrong_name):

    if not wrong_name:
        return None

    if re.search(r'\bS\d{1,2}\b|\bSeason\s*\d+', wrong_name, re.I):
        return None

    query = wrong_name.strip().lower()
    wrong_name = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", wrong_name)
    clean_query = re.sub(r"\b(19|20)\d{2}\b", "", wrong_name).strip()
	
    # ✅ cache only success
    cached = SPELL_CACHE.get(query)
    if cached:
        return cached

    try:
        search_results = imdb.search_movie(wrong_name)
        titles = []

        for m in search_results.titles:
            title = getattr(m, "title", None)
            if title and title not in titles:
                titles.append(title)

        # limit search pool
        titles = titles[:20]

        # sort by similarity
        from rapidfuzz import process, fuzz

        best = process.extract(
            clean_query,
            titles,
            scorer=fuzz.token_sort_ratio,
            limit=5
        )

        titles = [t[0] for t in best]
    except:
        return None

    if not titles:
        return None

    best_match = smart_match(clean_query, titles)
    if not best_match:
        return None

    try:
        result = await get_search_results(chat_id=chat_id, query=best_match)
    except:
        return None

    if not result or len(result) != 3:
        return None

    files, _, _ = result

    if not files:
        return None

    # ✅ only success cache
    SPELL_CACHE[query] = best_match

    if len(SPELL_CACHE) > CACHE_LIMIT:
        SPELL_CACHE.clear()

    return best_match

async def advantage_spell_chok(client, message):

    # 🔒 safety
    if not message.text or not isinstance(message.text, str):
        return

    search = clean_query(message.text)
    user_id = message.from_user.id if message.from_user else 0

    query = re.sub(
        r"\b(movie|send|file|new|latest|with|subtitle|pls|please|bro|full)\b",
        "",
        search,
        flags=re.IGNORECASE
    ).strip()

    if not query:
        return

    cache_key = query.lower()

    # ===============================
    # 🔥 CACHE
    # ===============================
    movies = POSTER_CACHE.get(cache_key)

    if movies is None:

        movies = []

        search_query = re.sub(r"\b(19|20)\d{2}\b", "", query).strip()
        try:
            raw = await get_poster(search_query, bulk=True)
        except Exception:
            raw = None

        # 🔥 iterable safety
        if raw:
            items = raw if isinstance(raw, (list, tuple)) else [raw]
        else:
            items = []

        titles = []
        seen = set()

        for m in items:

            mid = None
            title = None

            # dict style
            if isinstance(m, dict):
                mid = m.get("id") or m.get("imdb_id")
                title = m.get("title")

            # object style
            else:
                mid = getattr(m, "imdb_id", None) or getattr(m, "id", None)
                title = getattr(m, "title", None)

            if not mid or not title:
                continue

            # 🔥 duplicate remove
            if title.lower() in seen:
                continue

            seen.add(title.lower())
            titles.append((mid, title))

        # 🔥 nothing found
        if not titles:
            movies = []

        else:

            from rapidfuzz import process, fuzz

            # 🔥 remove year for better matching
            clean_query_text = re.sub(r"\b(19|20)\d{2}\b", "", query).strip().lower()
            # 🔥 exact match priority
            exact_match = None

            for mid, title in titles:
                main_title = title.lower().strip()
                query_title = clean_query_text

                # 1️⃣ exact match
                if main_title == query_title:
                    exact_match = (mid, title)
                    break

                # 2️⃣ partial english match
                if query_title in main_title:
                    exact_match = (mid, title)
                    break

                # 3️⃣ reverse match
                if main_title in query_title:
                    exact_match = (mid, title)
                    break

            if exact_match:
                movies.append(type("Movie", (), {
                    "imdb_id": str(exact_match[0]),
                    "title": exact_match[1]
                }))

            # 🔥 fuzzy sorting
            sorted_titles = process.extract(
                clean_query_text,
                [t[1] for t in titles],
                scorer=fuzz.token_sort_ratio,
                limit=15
            )

            seen_titles = set()
            english_titles = []
            other_titles = []

            if exact_match:
                seen_titles.add(exact_match[1].lower())

            for name, score, index in sorted_titles:

                if score < 35:
                    continue

                title_lower = name.lower()

                if title_lower in seen_titles:
                    continue

                mid = titles[index][0]

                # 🔥 detect english titles
                if re.fullmatch(r"[A-Za-z0-9 :'\-]+", name):
                    english_titles.append((mid, name))
                else:
                    other_titles.append((mid, name))

                seen_titles.add(title_lower)


            # 🔥 English titles first
            for mid, name in english_titles:
                movies.append(type("Movie", (), {
                    "imdb_id": str(mid),
                    "title": name
                }))

            # 🔥 Other language titles last
            for mid, name in other_titles:
                movies.append(type("Movie", (), {
                    "imdb_id": str(mid),
                    "title": name
                }))


            movies = movies[:6]    

        # 🔥 cache save
        if movies:
            POSTER_CACHE[cache_key] = movies

        if len(POSTER_CACHE) > CACHE_LIMIT:
            POSTER_CACHE.clear()

    # ===============================
    # 🔥 no result → fallback
    # ===============================
    if not movies:

        reply = await message.reply_text(
            f"<b>😕 sᴏʀʀʏ {message.from_user.mention},\n"
            f"ɪ ᴄᴏᴜʟᴅɴ'ᴛ ғɪɴᴅ ᴀɴʏᴛʜɪɴɢ ᴡɪᴛʜ ʏᴏᴜʀ sᴘᴇʟʟɪɴɢ.\n"
            f"ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ʏᴏᴜʀ sᴘᴇʟʟɪɴɢ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.</b>",
            reply_to_message_id=message.id
        )

        await asyncio.sleep(15)

        try:
            await reply.delete()
            await message.delete()
        except:
            pass

        return

    # ===============================
    # 🔥 build buttons
    # ===============================
    buttons = [
        [InlineKeyboardButton(m.title, callback_data=f"spol#{m.imdb_id}#{user_id}")]
        for m in movies
    ]

    buttons.append([
        InlineKeyboardButton("ᴄʟᴏsᴇ ʟɪsᴛ", callback_data=f"spellclose_secure_x9#{user_id}")
    ])

    msg = await message.reply_text(
        script.CUDNT_FND.format(message.from_user.mention),
        reply_markup=InlineKeyboardMarkup(buttons),
        reply_to_message_id=message.id
    )

    # 🔥 auto delete
    asyncio.create_task(auto_delete_spell(msg, message))
    

async def auto_delete_spell(bot_msg, user_msg, delay=25):
    await asyncio.sleep(delay)

    try:
        await bot_msg.delete()
    except:
        pass

    try:
        await user_msg.delete()
    except:
        pass

@Client.on_callback_query(filters.regex("^spellclose_secure_x9#"))
async def secure_spell_close_handler(client, query):

    try:
        _, owner = query.data.split("#")
        owner = int(owner)
    except:
        return

    if query.from_user.id != owner:
        return await query.answer("🚫 ɴᴏᴛ ғᴏʀ ʏᴏᴜ..", show_alert=False)

    try:
        await query.message.delete()
    except:
        pass
    try:
        if query.message.reply_to_message:
            await query.message.reply_to_message.delete()
    except:
        pass
