import os
import re, sys
import json
import base64
import random
import asyncio
import time
import pytz
from logging_helper import LOGGER
from .pm_filter import auto_filter 
from Script import script
from datetime import datetime, timedelta
from database.refer import referdb
from database.topdb import silentdb
from pyrogram.enums import ParseMode, ChatType
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import *
from database.ia_filterdb import *
from database.users_chats_db import db
from info import *
from utils import *
from .fsub_helper import check_force_subscription, is_req_subscribed, is_subscribed

TIMEZONE = "Asia/Kolkata"
BATCH_FILES = {}

# 🔐 Temporary store for del_files selection
DEL_FILES_SESSION = {}
DEL_FILES_PER_PAGE = 10

# 🔥 Words that should be removed from filename/caption
REMOVED_SPC_WORD = ["[SANKET]", "moviesmod", "HDWebMovies", "Telegram", "TG", "www.", "hdholly", "hdmovie2.productions", "twn4all", "hdmovie2", "ott_downloader_bot", "bollyflix", "[~ᴍᴋ™~]", "ExtraFlix.pw", "hdhub4u", "skymovieshd", "@Eliteflix", "t.me", "4kdbhub", "movies4u", "tw4all", "Hdhub4u", "cinevood", "skymoviedHD", "4khdhub", "Toonworld4all", "TW4ALL", "ExtraFlix", "Hdhub", "Movies4u", "movies4u", "Vegamovies", "extraflix", "Filmy4wap", "Filmu4cab", "Tamilmv", "CineVood", "Hub4u", "Hub4", "SkymoviesHD", "Skymovieshd", "telegram", "tg", "TG", "Telegram", "HdWebMovies", "mkvcinemas", "mkvCinemas", "mkvking", "5moviez", "hdm2", "mkvcinema", "1tamil", "1tamilmv", "1Tamil", "1tamilblaster", "1TamilBlaster", "Moviez", "moviez", "yts mx", "YTS", "YTS MX", "mkvCinem", "filmyzilla", "filmzilla", "CineVood", "BT MOVIES HD", "FILMSCLUB04", "XDMovies", "mp4movies", "mp4moviez", "MLWBD", "MLSBD", "mlsbd", "mlwbd", "FibWatch", "fibwatch", "Joya9tv", "joya9tv", "Cinedoze", "CineDoze", "cinedoze", "world4u", "SSRMovies", "SSRmovies", "5MovieRulz", "FilmyCab", "hdweb", "RymOfficial", "(Mᴏᴏɴ Kɴɪɢʜᴛ)", "mkvanime"] #[remove words form file name]

def human_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return "0B"


def extract_file_info(name: str):
    name = name.lower()

    # 🎬 episode (highest priority)
    ep = re.search(r"s\d{1,2}\s*e\d{1,2}", name)
    if ep:
        return ep.group().upper()

    # 📺 season
    season = re.search(r"s\d{1,2}", name)
    if season:
        return season.group().upper()

    # 🎞 quality (movies / fallback)
    quality = re.search(r"(2160p|1080p|720p|480p|360p|240p)", name)
    if quality:
        return quality.group()

    return None

def clean_special_words(text: str) -> str:
    """
    Remove unwanted special words from filename or caption
    """
    if not text:
        return text

    cleaned = text
    for word in REMOVED_SPC_WORD:
        # 🔥 case-insensitive replace
        cleaned = re.sub(
            re.escape(word),
            "",
            cleaned,
            flags=re.IGNORECASE
        )

    # 🔧 extra space cleanup
    cleaned = re.sub(r"[\t]", " ", cleaned).strip()
    return cleaned

def build_del_files_buttons(session):
    page = session["page"]
    files = session["files"]
    selected = session["selected"]

    start = page * DEL_FILES_PER_PAGE
    end = start + DEL_FILES_PER_PAGE
    page_files = files[start:end]

    buttons = []

    # 📂 file buttons (WITH SIZE + QUALITY / SEASON / EP)
    for f in page_files:
        fid = str(f["_id"])
        mark = "✅" if fid in selected else "⬜"

        name = f.get("file_name", "Unknown")
        raw_size = (
            f.get("file_size")
            or f.get("fileSize")
            or f.get("size")
            or 0
                )
        try:
            size = human_size(int(raw_size))
        except Exception:
            size = "N/A"
        info = extract_file_info(name)
        short_name = name[:45] + "…" if len(name) > 45 else name

        if info:
            text = f"{mark} [{info} | {size}] {short_name}"
        else:
            text = f"{mark} [{size}] {short_name}"

        buttons.append([
            InlineKeyboardButton(
                text,
                callback_data=f"df_toggle:{fid}"
            )
        ])
    # 🔁 page info
    total_pages = (len(files) - 1) // DEL_FILES_PER_PAGE + 1

    # ⏮ navigation
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("☜︎︎︎ ᴘʀᴇᴠ", callback_data="df_prev"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("ɴᴇxᴛ ☞︎︎︎", callback_data="df_next"))
    buttons.append(nav)

    # ☑️ select controls
    buttons.append([
        InlineKeyboardButton("sᴇʟᴇᴄᴛ ᴀʟʟ", callback_data="df_select_all"),
        InlineKeyboardButton("ᴜɴsᴇʟᴇᴄᴛ ᴀʟʟ", callback_data="df_unselect_all")
    ])

    # ✅ confirm
    buttons.append([
        InlineKeyboardButton("✅ ᴄᴏɴғɪʀᴍ ᴘʀᴏᴄᴇss", callback_data="df_confirm"),
        InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="df_cancel")
    ])

    return InlineKeyboardMarkup(buttons)

async def send_file_pipeline(client, query, file_id, grp_id):

    files_ = await get_file_details(file_id)
    if not files_:
        return

    files = files_[0]

    title = clean_special_words(clean_filename(files.file_name))
    size = get_size(files.file_size)

    f_caption = files.caption

    settings = await get_settings(int(grp_id))
    DELETE_TIME = settings.get("auto_del_time", AUTO_DELETE_TIME)
    SILENTX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)

    if SILENTX_CAPTION:
        try:
            original_caption = files.caption
            fallback_caption = original_caption if original_caption else title

            f_caption = SILENTX_CAPTION.format(
                file_name=title or "",
                file_size=size or "",
                file_caption=fallback_caption
            )

            f_caption = clean_special_words(f_caption)

        except Exception:
            pass

    if f_caption is None:
        f_caption = clean_special_words(clean_filename(files.file_name))

    if STREAM_MODE:
        btn = [
            [InlineKeyboardButton('𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝗍𝗋𝖾𝖺𝗆𝗂𝗇𝗀 𝖫𝗂𝗇𝗄', callback_data=f'streamfile:{file_id}')],
            [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅', url=UPDATE_CHANNEL_LNK)],
            [InlineKeyboardButton("📊 𝗩𝗶𝗲𝘄 𝗔𝘂𝗱𝗶𝗼/𝗦𝘂𝗯𝘁𝗶𝘁𝗹𝗲 𝗜𝗻𝗳𝗼", callback_data="trackinfo")]
        ]
    else:
        btn = [
            [InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=UPDATE_CHANNEL_LNK)],
            [InlineKeyboardButton("📑 ᴠɪᴇᴡ ᴀᴜᴅɪᴏ/sᴜʙᴛɪᴛʟᴇ ᴅᴇᴛᴀɪʟs", callback_data="trackinfo")]
        ]

    try:
        msg = await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            parse_mode=enums.ParseMode.HTML,
            protect_content=settings.get('file_secure', PROTECT_CONTENT),
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except:
        return

    k = await client.send_message(
        chat_id=query.from_user.id,
        text=(
            f"<b><u>❗️IMPORTANT❗️</u>\n\n"
            f"ᴛʜɪꜱ ꜰɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ {get_time(DELETE_TIME)} 🫥\n\n"
            f"ᴘʟᴇᴀꜱᴇ ꜰᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ꜰɪʟᴇ ꜱᴏᴍᴇᴡʜᴇʀᴇ ᴇʟꜱᴇ.</b>"
        ),
        parse_mode=enums.ParseMode.HTML
    )

    await asyncio.sleep(DELETE_TIME)

    try:
        await msg.delete()
    except:
        pass

    try:
        await k.edit_text(
            "<b>ʏᴏᴜʀ ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!</b>",
            parse_mode=enums.ParseMode.HTML
        )
    except:
        pass   
    
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    bot_id = client.me.id
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception:
            pass
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    m = message
    if len(m.command) == 2 and m.command[1].startswith(('notcopy', 'sendall')):
        _, userid, verify_id, file_id = m.command[1].split("_", 3)
        user_id = int(userid)
        grp_id = temp.VERIFICATIONS.get(user_id, 0)
        settings = await get_settings(grp_id)         
        verify_id_info = await db.get_verify_id_info(user_id, verify_id)
        if not verify_id_info or verify_id_info["verified"]:
            await message.reply("<b>ʟɪɴᴋ ᴇxᴘɪʀᴇᴅ ᴛʀʏ ᴀɢᴀɪɴ...</b>")
            return  
        ist_timezone = pytz.timezone('Asia/Kolkata')
        if await db.user_verified(user_id):
            key = "third_time_verified"
        else:
            key = "second_time_verified" if await db.is_user_verified(user_id) else "last_verified"
        current_time = datetime.now(tz=ist_timezone)
        result = await db.update_notcopy_user(user_id, {key:current_time})
        await db.update_verify_id_info(user_id, verify_id, {"verified":True})
        if key == "third_time_verified": 
            num = 3 
        else: 
            num =  2 if key == "second_time_verified" else 1 
        if key == "third_time_verified": 
            msg = script.THIRDT_VERIFY_COMPLETE_TEXT
        else:
            msg = script.SECOND_VERIFY_COMPLETE_TEXT if key == "second_time_verified" else script.VERIFY_COMPLETE_TEXT
        if message.command[1].startswith('sendall'):
            verifiedfiles = f"https://telegram.me/{temp.U_NAME}?start=allfiles_{grp_id}_{file_id}"
        else:
            verifiedfiles = f"https://telegram.me/{temp.U_NAME}?start=file_{grp_id}_{file_id}"
        await client.send_message(settings['log'], script.VERIFIED_LOG_TEXT.format(m.from_user.mention, user_id, datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %B %Y'), num))
        btn = [[
            InlineKeyboardButton("✅ ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ɢᴇᴛ ꜰɪʟᴇ ✅", url=verifiedfiles),
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        dlt=await m.reply_photo(
            photo=(VERIFY_IMG),
            caption=msg.format(message.from_user.mention, get_readable_time(TWO_VERIFY_GAP)),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await asyncio.sleep(300)
        await dlt.delete()
        return         
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        alive_msg=await message.reply_text("I Am Alive..")
        await asyncio.sleep(5)
        await alive_msg.delete()
        if not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))       
            await db.add_chat(message.chat.id, message.chat.title)
        return 
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))
    if len(message.command) == 1:
        buttons = get_main_buttons()
        current_time = datetime.now(pytz.timezone(TIMEZONE))
        curr_time = current_time.hour        
        if curr_time < 12:
            gtxt = "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ 🌞" 
        elif curr_time < 17:
            gtxt = "ɢᴏᴏᴅ ᴀғᴛᴇʀɴᴏᴏɴ 🌓" 
        elif curr_time < 21:
            gtxt = "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌘"
        else:
            gtxt = "ɢᴏᴏᴅ ɴɪɢʜᴛ 🌑"

        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(user=message.from_user.mention, greet=gtxt),
                
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
        return
        
    if len(message.command) == 2 and message.command[1].startswith("reff_"):
        try:
            user_id = int(message.command[1].split("_")[1])
        except ValueError:
            await message.reply_text("Invalid refer!")
            return
        if user_id == message.from_user.id:
            await message.reply_text("Hᴇʏ Dᴜᴅᴇ, Yᴏᴜ Cᴀɴ'ᴛ Rᴇғᴇʀ Yᴏᴜʀsᴇʟғ 🤣!\n\nsʜᴀʀᴇ ʟɪɴᴋ ʏᴏᴜʀ ғʀɪᴇɴᴅ ᴀɴᴅ ɢᴇᴛ 10 ʀᴇғᴇʀʀᴀʟ ᴘᴏɪɴᴛ ɪғ ʏᴏᴜ ᴀʀᴇ ᴄᴏʟʟᴇᴄᴛɪɴɢ 100 ʀᴇғᴇʀʀᴀʟ ᴘᴏɪɴᴛs ᴛʜᴇɴ ʏᴏᴜ ᴄᴀɴ ɢᴇᴛ 1 ᴍᴏɴᴛʜ ғʀᴇᴇ ᴘʀᴇᴍɪᴜᴍ ᴍᴇᴍʙᴇʀsʜɪᴘ.")
            return
        if referdb.is_user_in_list(message.from_user.id):
            await message.reply_text("Yᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ᴀʟʀᴇᴀᴅʏ ɪɴᴠɪᴛᴇᴅ ❗")
            return
        if await db.is_user_exist(message.from_user.id): 
            await message.reply_text("‼️ Yᴏᴜ Hᴀᴠᴇ Bᴇᴇɴ Aʟʀᴇᴀᴅʏ Iɴᴠɪᴛᴇᴅ ᴏʀ Jᴏɪɴᴇᴅ")
            return 
        try:
            uss = await client.get_users(user_id)
        except Exception:
            return 	    
        referdb.add_user(message.from_user.id)
        fromuse = referdb.get_refer_points(user_id) + 10
        if fromuse == 100:
            referdb.add_refer_points(user_id, 0) 
            await message.reply_text(f"🎉 𝗖𝗼𝗻𝗴𝗿𝗮𝘁𝘂𝗹𝗮𝘁𝗶𝗼𝗻𝘀! 𝗬𝗼𝘂 𝘄𝗼𝗻 𝟭𝟬 𝗥𝗲𝗳𝗲𝗿𝗿𝗮𝗹 𝗽𝗼𝗶𝗻𝘁 𝗯𝗲𝗰𝗮𝘂𝘀𝗲 𝗬𝗼𝘂 𝗵𝗮𝘃𝗲 𝗯𝗲𝗲𝗻 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝗜𝗻𝘃𝗶𝘁𝗲𝗱 ☞ {uss.mention}!")		    
            await client.send_message(chat_id=user_id, text=f"You have been successfully invited by {message.from_user.mention}!") 	
            seconds = 2592000
            if seconds > 0:
                expiry_time = datetime.now() + timedelta(seconds=seconds)
                user_data = {"id": user_id, "expiry_time": expiry_time}
                await db.update_user(user_data)		    
                await client.send_message(
                    chat_id=user_id,
                    text=f"<b>Hᴇʏ {uss.mention}\n\nYᴏᴜ ɢᴏᴛ 1 ᴍᴏɴᴛʜ ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʙʏ ɪɴᴠɪᴛɪɴɢ 10 ᴜsᴇʀs ❗", disable_web_page_preview=True              
                )
            for admin in ADMINS:
                await client.send_message(chat_id=admin, text=f"Sᴜᴄᴄᴇss ғᴜʟʟʏ ᴛᴀsᴋ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ʙʏ ᴛʜɪs ᴜsᴇʀ:\n\nuser Nᴀᴍᴇ: {uss.mention}\n\nUsᴇʀ ɪᴅ: {uss.id}!")	
        else:
            referdb.add_refer_points(user_id, fromuse)
            await message.reply_text(f"You have been successfully invited by {uss.mention}!")
            await client.send_message(chat_id=user_id, text=f"𝗖𝗼𝗻𝗴𝗿𝗮𝘁𝘂𝗹𝗮𝘁𝗶𝗼𝗻𝘀! 𝗬𝗼𝘂 𝘄𝗼𝗻 𝟭𝟬 𝗥𝗲𝗳𝗲𝗿𝗿𝗮𝗹 𝗽𝗼𝗶𝗻𝘁 𝗯𝗲𝗰𝗮𝘂𝘀𝗲 𝗬𝗼𝘂 𝗵𝗮𝘃𝗲 𝗯𝗲𝗲𝗻 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝗜𝗻𝘃𝗶𝘁𝗲𝗱 ☞{message.from_user.mention}!")
        return
        
    if len(message.command) == 2 and message.command[1].startswith('getfile'):
        movies = message.command[1].split("-", 1)[1] 
        movie = movies.replace('-',' ')
        message.text = movie 
        await auto_filter(client, message) 
        return
            
    data = message.command[1]
    try:
        pre, grp_id, file_id = data.split('_', 2)
    except:
        pre, grp_id, file_id = "", 0, data

    try:
        #settings = await get_settings(int(data.split("_", 2)[1]))

        settings = await get_settings(int(grp_id))

        # 🔹 Group level
        direct_fsubs = settings.get('fsub_id') or []
        req_fsubs = settings.get('req_fsub_id') or []

        if not isinstance(direct_fsubs, list):
            direct_fsubs = [direct_fsubs]

        if not isinstance(req_fsubs, list):
            req_fsubs = [req_fsubs]

        # 🔹 Import Global
        from info import GLOBAL_FSUB_CHANNELS, GLOBAL_REQ_FSUB_CHANNELS

        # 🔹 Merge Global + Group
        direct_fsubs += GLOBAL_FSUB_CHANNELS
        req_fsubs += GLOBAL_REQ_FSUB_CHANNELS

        # 🔹 Remove duplicates (order safe)
        direct_fsubs = list(dict.fromkeys(direct_fsubs))
        req_fsubs = list(dict.fromkeys(req_fsubs))

        fsub_ids = []

        for ch in direct_fsubs:
            if ch:
                fsub_ids.append((ch, False))

        for ch in req_fsubs:
            if ch:
                fsub_ids.append((ch, True))

        if not fsub_ids:
            return# 🔥 nothing set → skip force sub

        tasks = [
            check_force_subscription(
                client,
                message.from_user.id,
                chnl,
                is_req,
                is_subscribed,
                is_req_subscribed,
                message
            )
            for chnl, is_req in fsub_ids
        ]

        results = await asyncio.gather(*tasks)

        btn = []
        i = 1

        for res in results:
            if res:
                btn.append([
                    InlineKeyboardButton(
                        f"⛔️ {i}. {res['title']} ⛔️",
                        url=res['url']
                    )
                ])
                i += 1

        if btn:
            btn.append([
                InlineKeyboardButton(
                    "♻️ ᴛʀʏ ᴀɢᴀɪɴ ♻️",
                    url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}"
                )
            ])

            await client.send_photo(
                chat_id=message.from_user.id,
                photo=random.choice(FSUB_IMG),
                caption=script.FORCESUB_TEXT,
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML,
            )
            return
        

    except Exception as e:
        await log_error(client, f"Got Error In Force Subscription Function.\n\n Error - {e}")
        LOGGER.error(f"Error In Fsub :- {e}")
        
    user_id = m.from_user.id
    if not await db.has_premium_access(user_id):
        try:
            grp_id = int(grp_id)
            user_verified = await db.is_user_verified(user_id)
            settings = await get_settings(grp_id)
            is_second_shortener = await db.use_second_shortener(user_id, settings.get('verify_time', TWO_VERIFY_GAP)) 
            is_third_shortener = await db.use_third_shortener(user_id, settings.get('third_verify_time', THREE_VERIFY_GAP))
            if settings.get("is_verify", IS_VERIFY) and (not user_verified or is_second_shortener or is_third_shortener):                
                verify_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
                await db.create_verify_id(user_id, verify_id)
                temp.VERIFICATIONS[user_id] = grp_id
                if message.command[1].startswith('allfiles'):
                    verify = await get_shortlink(f"https://telegram.me/{temp.U_NAME}?start=sendall_{user_id}_{verify_id}_{file_id}", grp_id, is_second_shortener, is_third_shortener)
                else:
                    verify = await get_shortlink(f"https://telegram.me/{temp.U_NAME}?start=notcopy_{user_id}_{verify_id}_{file_id}", grp_id, is_second_shortener, is_third_shortener)
                if is_third_shortener:
                    howtodownload = settings.get('tutorial_3', TUTORIAL_3)
                else:
                    howtodownload = settings.get('tutorial_2', TUTORIAL_2) if is_second_shortener else settings.get('tutorial', TUTORIAL)
                buttons = [[
                    InlineKeyboardButton(text="♻️ ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ᴠᴇʀɪꜰʏ ♻️", url=verify)
                ],[
                    InlineKeyboardButton(text="⁉️ ʜᴏᴡ ᴛᴏ ᴠᴇʀɪꜰʏ ⁉️", url=howtodownload)
                ]]
                reply_markup=InlineKeyboardMarkup(buttons)
                if await db.user_verified(user_id): 
                    msg = script.THIRDT_VERIFICATION_TEXT
                else:            
                    msg = script.SECOND_VERIFICATION_TEXT if is_second_shortener else script.VERIFICATION_TEXT
                n=await m.reply_text(
                    text=msg.format(message.from_user.mention),
                    protect_content = True,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                await asyncio.sleep(300) 
                await n.delete()
                await m.delete()
                return
        except Exception as e:
            await log_error(client, f"Got Error In Verification Funtion.\n\n Error - {e}")
            LOGGER.error(f"Error In Verification - {e}")
            pass
    
    if data.startswith("allfiles"):
        files = temp.GETALL.get(file_id)
        if not files:
            return await message.reply('<b><i>ɴᴏ ꜱᴜᴄʜ ꜰɪʟᴇ ᴇxɪꜱᴛꜱ !</b></i>')
        filesarr = []
        for file in files:
            file_id = file.file_id
            files_ = await get_file_details(file_id)
            files1 = files_[0]
            title = clean_special_words(clean_filename(files1.file_name)) 
            size = get_size(files1.file_size)
            f_caption = files1.caption
            settings = await get_settings(int(grp_id))
            DELETE_TIME = settings.get("auto_del_time", AUTO_DELETE_TIME)
            SILENTX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
            if SILENTX_CAPTION:
                try:
                    original_caption = files1.caption
                    fallback_caption = original_caption if original_caption else title
                    f_caption = SILENTX_CAPTION.format(file_name=title or "",file_size=size or "",file_caption=fallback_caption)
                    # 🔥 FINAL caption user দেখবে → clean here
                    f_caption = clean_special_words(f_caption)
                except Exception as e:
                    LOGGER.exception("Caption format failed")
                    f_caption = f_caption
            if f_caption is None:
                f_caption = clean_special_words(clean_filename(files1.file_name)) 
            if STREAM_MODE:
                btn = [
                    [InlineKeyboardButton('𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝗍𝗋𝖾𝗆𝗂𝗇𝗀 𝖫𝗂𝗇𝗄', callback_data=f'streamfile:{file_id}')],
                    [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅', url=UPDATE_CHANNEL_LNK)],
                    [InlineKeyboardButton("📊 𝗩𝗶𝗲𝘄 𝗔𝘂𝗱𝗶𝗼/𝗦𝘂𝗯𝘁𝗶𝘁𝗲𝗹 𝗜𝗻𝗳𝗼", callback_data="trackinfo")]
                ]
            else:
                btn = [
                    [InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=UPDATE_CHANNEL_LNK)],
                    [InlineKeyboardButton("📑 ᴠɪᴇᴡ ᴀᴜᴅɪᴏ/sᴜʙᴛɪᴛᴇʟ ᴅᴇᴛᴀɪʟs", callback_data="trackinfo")]
                ]
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=settings.get('file_secure', PROTECT_CONTENT),
                reply_markup=InlineKeyboardMarkup(btn)
            )
            filesarr.append(msg)
        k = await client.send_message(chat_id=message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nᴛʜɪꜱ ᴍᴏᴠɪᴇ ꜰɪʟᴇ/ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b><u><code>{get_time(DELETE_TIME)}</code></u> 🫥 <i></b>(ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ)</i>.\n\n<b><i>ᴘʟᴇᴀꜱᴇ ꜰᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ꜰɪʟᴇ ᴛᴏ ꜱᴏᴍᴇᴡʜᴇʀᴇ ᴇʟꜱᴇ ᴀɴᴅ ꜱᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴛʜᴇʀᴇ</i></b>")
        await asyncio.sleep(DELETE_TIME)
        for x in filesarr:
            await x.delete()
        await k.edit_text("<b>ʏᴏᴜʀ ᴀʟʟ ᴠɪᴅᴇᴏꜱ/ꜰɪʟᴇꜱ ᴀʀᴇ ᴅᴇʟᴇᴛᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ !\nᴋɪɴᴅʟʏ ꜱᴇᴀʀᴄʜ ᴀɢᴀɪɴ</b>")
        return

    user = message.from_user.id
    files_ = await get_file_details(file_id)  
    settings = await get_settings(int(grp_id))
    if not files_:
        try:
            decoded = base64.urlsafe_b64decode(
                data + "=" * (-len(data) % 4)
            ).decode("utf-8", errors="ignore")

            pre, file_id = decoded.split("_", 1)

        except Exception as e:
            LOGGER.error(f"Start param decode failed: {e}")
            return
        try:
            if STREAM_MODE:
                btn = [
                    [InlineKeyboardButton('𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝗍𝗋𝖾𝗆𝗂𝗇𝗀 𝖫𝗂𝗇𝗄', callback_data=f'streamfile:{file_id}')],
                    [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅', url=UPDATE_CHANNEL_LNK)],
                    [InlineKeyboardButton("📊 𝗩𝗶𝗲𝘄 𝗔𝘂𝗱𝗶𝗼/𝗦𝘂𝗯𝘁𝗶𝘁𝗲𝗹 𝗜𝗻𝗳𝗼", callback_data="trackinfo")]
                ]
            else:
                btn = [
                    [InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=UPDATE_CHANNEL_LNK)],
                    [InlineKeyboardButton("📑 ᴠɪᴇᴡ ᴀᴜᴅɪᴏ/sᴜʙᴛɪᴛᴇʟ ᴅᴇᴛᴀɪʟs", callback_data="trackinfo")]
                ]
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                protect_content=settings.get('file_secure', PROTECT_CONTENT),
                reply_markup=InlineKeyboardMarkup(btn))

            filetype = msg.media
            file = getattr(msg, filetype.value)
            title = clean_special_words(clean_filename(file.file_name))              
            size=get_size(file.file_size)
            f_caption = f"<code>{title}</code>"
            settings = await get_settings(int(grp_id))
            DELETE_TIME = settings.get("auto_del_time", AUTO_DELETE_TIME)
            SILENTX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
            if SILENTX_CAPTION:
                try:
                    f_caption=SILENTX_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='')
                    f_caption = clean_special_words(f_caption)
                except:
                    return
            await msg.edit_caption(f_caption)
            k = await msg.reply(f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u>\n\n ᴛʜɪꜱ ᴍᴏᴠɪᴇ ꜰɪʟᴇ/ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ {get_time(DELETE_TIME)} 🫥 (ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ).\n\n ғᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ғɪʟᴇs ᴛo sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ ᴀɴᴅ sᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴛʜᴇʀᴇ.</b>", quote=True)
            await asyncio.sleep(DELETE_TIME)
            await msg.delete()
            await k.edit_text("<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!</b>")
            return
        except:
            pass
        return await message.reply('ɴᴏ ꜱᴜᴄʜ ꜰɪʟᴇ ᴇxɪꜱᴛꜱ !')
    
    files = files_[0]
    title = clean_special_words(clean_filename(files.file_name))
    size = get_size(files.file_size)
    f_caption = files.caption
    settings = await get_settings(int(grp_id))
    # ✅ DAILY LIMIT CHECK (single file only)
    user_id = message.from_user.id
    if DAILY_LIMIT:
        is_limit_less = user_id in LIMIT_LESS_USERS
        is_premium = await db.has_premium_access(message.from_user.id)
        if not is_limit_less and not is_premium:
            if not check_daily_limit(message.from_user.id, DAILY_TOTAL_LIMIT):
                await message.reply_text(
                    f"🚫 <b>ᴅᴀɪʟʏ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ</b>\n\n"
                    f"<b>ʏᴏᴜ ᴄᴀɴ ᴅᴏᴡɴʟᴏᴀᴅ ᴏɴʟʏ {DAILY_TOTAL_LIMIT} ғɪʟᴇs ᴘᴇʀ ᴅᴀʏ</b>.\n"
                    f"<b>ᴛʀʏ ᴀɢᴀɪɴ ᴛᴏᴍᴏʀʀᴏᴡ 😋</b>",
                    parse_mode=enums.ParseMode.HTML
                )
                return
    DELETE_TIME = settings.get("auto_del_time", AUTO_DELETE_TIME)
    SILENTX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
    if SILENTX_CAPTION:
        try:
            original_caption = files.caption
            fallback_caption = original_caption if original_caption else title

            f_caption = SILENTX_CAPTION.format(file_name=title or "",file_size=size or "",file_caption=fallback_caption)

            # 🔥 REMOVE SPECIAL WORDS FROM FINAL CAPTION
            f_caption = clean_special_words(f_caption)
        except Exception as e:
            LOGGER.error(e)
            f_caption = f_caption

    if f_caption is None:
        f_caption = clean_special_words(clean_filename(files.file_name))
    if STREAM_MODE:
        btn = [
            [InlineKeyboardButton('𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝗍𝗋𝖾𝗆𝗂𝗇𝗀 𝖫𝗂𝗇𝗄', callback_data=f'streamfile:{file_id}')],
            [InlineKeyboardButton('𝖴𝗉𝖽𝖺𝗍𝖾 𝖢𝗁𝖺𝗇𝗇𝖾𝗅', url=UPDATE_CHANNEL_LNK)],
            [InlineKeyboardButton("📊 𝗩𝗶𝗲𝘄 𝗔𝘂𝗱𝗶𝗼/𝗦𝘂𝗯𝘁𝗶𝘁𝗲𝗹 𝗜𝗻𝗳𝗼", callback_data="trackinfo")]
        ]
    else:
        btn = [
            [InlineKeyboardButton('📌 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=UPDATE_CHANNEL_LNK)],
            [InlineKeyboardButton("📑 ᴠɪᴇᴡ ᴀᴜᴅɪᴏ/sᴜʙᴛɪᴛᴇʟ ᴅᴇᴛᴀɪʟs", callback_data="trackinfo")]
        ]
    msg = await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=settings.get('file_secure', PROTECT_CONTENT),
        reply_markup=InlineKeyboardMarkup(btn)
    )

    #k = await msg.reply(f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u>\n\n ᴛʜɪꜱ ᴍᴏᴠɪᴇ ꜰɪʟᴇ/ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ {get_time(DELETE_TIME)} 🫥 (ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ).\n\n ғᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ғɪʟᴇs ᴛo sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ ᴀɴᴅ sᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴛʜᴇʀᴇ.</b>", quote=True)     

    # ✅ DAILY LIMIT COUNT (single file only)
    user_id = message.from_user.id

    if DAILY_LIMIT:
        is_limit_less = user_id in LIMIT_LESS_USERS
        is_premium = await db.has_premium_access(user_id)

        if not is_limit_less and not is_premium:
            increase_daily_count(user_id)
    k = await msg.reply(f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u>\n\n ᴛʜɪꜱ ᴍᴏᴠɪᴇ ꜰɪʟᴇ/ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ {get_time(DELETE_TIME)} 🫥 (ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ).\n\n ғᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ғɪʟᴇs ᴛo sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ ᴀɴᴅ sᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴛʜᴇʀᴇ.</b>", quote=True)     
    await asyncio.sleep(DELETE_TIME)
    await msg.delete()
    await k.edit_text("<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!</b>")
    return

@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    log_path = "log.txt"

    if not os.path.exists(log_path):
        return await message.reply("❌ Log file not found")

    await message.reply_document(
        document=log_path,
        caption="📄 Bot Logs"
    )

@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):

    text = (
        "📚 <b>Search Guide</b>\n\n"

        "🎬 <b>Movies:</b>\n"
        "• Movie Name + Year\n"
        "• Example → <code>RRR 2022</code>\n\n"

        "📺 <b>Series:</b>\n"
        "• Name + Season → <code>Kurukshetra S01</code>\n"
        "• Episode → <code>Kurukshetra S01E05</code>\n\n"

        "⚡ <b>Tips for better results:</b>\n"
        "• Don't use special symbols → <code>: ; ' \" * , . - _ #</code>\n"
        "• If the title is long, search using only first 3–4 words\n"
        "• You can add quality/language → <code>1080p Hindi Tamil</code>\n\n"

        "🍿 <b>Send your query now!</b>"
    )

    btn = [[
        InlineKeyboardButton("📩 ʀᴇǫᴜᴇsᴛ ʜᴇʀᴇ", url=GRP_LNK)
    ]]

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(btn),
        disable_web_page_preview=True
    )

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete(bot, message):
    """Delete file from database"""
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Pʀᴏᴄᴇssɪɴɢ...⏳", quote=True)
    else:
        await message.reply('Rᴇᴘʟʏ ᴛᴏ ғɪʟᴇ ᴡɪᴛʜ /delete ᴡʜɪᴄʜ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ', quote=True)
        return
    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media:
            break
    else:
        await msg.edit('Tʜɪs ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ғɪʟᴇ ғᴏʀᴍᴀᴛ')
        return    
    file_id, file_ref = unpack_new_file_id(media.file_id)
    result = await Media.collection.delete_one({'_id': file_id})
    if not result.deleted_count and MULTIPLE_DB:
        result = await Media2.collection.delete_one({'_id': file_id})
    if result.deleted_count:
        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
        return
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    result = await Media.collection.delete_many({
        'file_name': file_name,
        'file_size': media.file_size,
        'mime_type': media.mime_type
    })
    if not result.deleted_count and MULTIPLE_DB:
        result = await Media2.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        })
    if result.deleted_count:
        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
        return
    result = await Media.collection.delete_many({
        'file_name': media.file_name,
        'file_size': media.file_size,
        'mime_type': media.mime_type
    })
    if not result.deleted_count and MULTIPLE_DB:
        result = await Media2.collection.delete_many({
            'file_name': media.file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        })
    if result.deleted_count:
        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
    else:
        await msg.edit('Fɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ ❌')

@Client.on_message(filters.command("del_files") & filters.user(ADMINS))
async def del_files_handler(client, message):
    if len(message.command) < 2:
        return await message.reply(
            "❌ Usage:\n/del_files movie_name",
            quote=True
        )

    query = " ".join(message.command[1:]).strip()

    # 🔎 search files by name
    files = await Media.collection.find(
        {"file_name": {"$regex": query, "$options": "i"}}
    ).to_list(length=None)

    if not files:
        return await message.reply(
            "❌ No matching files found",
            quote=True
        )

    # 🧠 session init
    DEL_FILES_SESSION[message.from_user.id] = {
        "files": files,
        "selected": set(),
        "page": 0
    }

    session = DEL_FILES_SESSION[message.from_user.id]

    await message.reply(
        f"🗂 Found {len(files)} files\n\nSelect files to delete:",
        reply_markup=build_del_files_buttons(session),
        quote=True
    )

@Client.on_callback_query(filters.regex("^df_"))
async def del_files_callback(client, callback):
    user_id = callback.from_user.id
    session = DEL_FILES_SESSION.get(user_id)

    # ❌ session না থাকলে
    if not session:
        return await callback.answer(
            "❌ Session expired",
            show_alert=True
        )

    data = callback.data

    # 🔁 SINGLE FILE TOGGLE
    if data.startswith("df_toggle:"):
        file_id = data.split(":", 1)[1]

        if file_id in session["selected"]:
            session["selected"].remove(file_id)
        else:
            session["selected"].add(file_id)

    # ☑️ SELECT ALL
    elif data == "df_select_all":
        if len(session["selected"]) == len(session["files"]):
            return await callback.answer(
                "ℹ️ All files already selected",
                show_alert=True
            )
        session["selected"] = set(str(f["_id"]) for f in session["files"])
    # ⬜ UNSELECT ALL
    elif data == "df_unselect_all":
        if not session["selected"]:
            return await callback.answer(
                "⚠️ Nothing selected",
                show_alert=True
            )
        session["selected"].clear()

    # ❌ CANCEL DELETE
    elif data == "df_cancel":
        DEL_FILES_SESSION.pop(user_id, None)
        await callback.message.edit_text("❌ Delete cancelled")
        return await callback.answer("Cancelled")

    # ➡️ NEXT PAGE
    elif data == "df_next":
        max_page = (len(session["files"]) - 1) // DEL_FILES_PER_PAGE
        if session["page"] < max_page:
            session["page"] += 1

    # ⬅️ PREV PAGE
    elif data == "df_prev":
        if session["page"] > 0:
            session["page"] -= 1

    # ✅ CONFIRM DELETE
    elif data == "df_confirm":
        ids = list(session["selected"])

        if not ids:
            return await callback.answer(
                "⚠️ No file selected",
                show_alert=True
            )

        # 🗑 delete from main DB
        await Media.collection.delete_many(
            {"_id": {"$in": ids}}
        )

        # 🗑 delete from second DB (if enabled)
        if MULTIPLE_DB:
            await Media2.collection.delete_many(
                {"_id": {"$in": ids}}
            )

        DEL_FILES_SESSION.pop(user_id, None)

        await callback.message.edit_text(
            f"✅ Deleted {len(ids)} selected files"
        )
        return await callback.answer("Done")

    await callback.message.edit_reply_markup(
        build_del_files_buttons(session)
    )
    await callback.answer()

@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'ᴛʜɪꜱ ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ ᴀʟʟ ʏᴏᴜʀ ɪɴᴅᴇxᴇᴅ ꜰɪʟᴇꜱ !\nᴅᴏ ʏᴏᴜ ꜱᴛɪʟʟ ᴡᴀɴᴛ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ?',
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⚠️ ʏᴇꜱ ⚠️", callback_data="autofilter_delete"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ ɴᴏ ❌", callback_data="close_data"
                    )
                ],
            ]
        ),
        quote=True,
    )

@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    if MULTIPLE_DB:    
        await Media2.collection.drop()
    await message.answer("Eᴠᴇʀʏᴛʜɪɴɢ's Gᴏɴᴇ")
    await message.message.edit('ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ᴀʟʟ ɪɴᴅᴇxᴇᴅ ꜰɪʟᴇꜱ ✅')

@Client.on_message(filters.command('settings'))
async def settings(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await message.reply(f"ʏᴏᴜ'ʀᴇ ᴀɴᴏɴʏᴍᴏᴜꜱ ᴀᴅᴍɪɴ.")
    chat_type = message.chat.type
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        if not await is_check_admin(client, grp_id, message.from_user.id):
            return await message.reply_text('<b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ</b>')
        await db.connect_group(grp_id, user_id)
        btn = [[
                InlineKeyboardButton("❤️‍🔥 ᴏᴘᴇɴ ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ ❤️‍🔥", callback_data=f"opnsetpm#{grp_id}")
              ],[
                InlineKeyboardButton("⚡ ᴏᴘᴇɴ ʜᴇʀᴇ ⚡", callback_data=f"opnsetgrp#{grp_id}")
              ]]
        await message.reply_text(
                text="<b>ᴡʜᴇʀᴇ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴏᴘᴇɴ ꜱᴇᴛᴛɪɴɢꜱ ᴍᴇɴᴜ ? ⚙️</b>",
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=message.id
        )
    elif chat_type == enums.ChatType.PRIVATE:
        connected_groups = await db.get_connected_grps(user_id)
        if not connected_groups:
            return await message.reply_text("No Connected Groups Found .")
        group_list = []
        for group in connected_groups:
            try:
                silentx = await client.get_chat(group)
                group_list.append([
                    InlineKeyboardButton(text=silentx.title, callback_data=f"grp_pm#{silentx.id}")
                ])
            except Exception as e:
                LOGGER.error(f"Error In PM Settings Button - {e}")
                pass
        await message.reply_text('Here Is Your Connected Groups.', reply_markup=InlineKeyboardMarkup(group_list))
                                                                                                            

@Client.on_message(filters.command('reload'))
async def connect_group(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    user_id = message.from_user.id
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.connect_group(message.chat.id, user_id)
        await message.reply_text("Group Reloaded ✅ Now You Can Manage This Group From PM.")
    elif message.chat.type == enums.ChatType.PRIVATE:
        if len(message.command) < 2:
            await message.reply_text("Use: /reload <group_id>")
            return
        try:
            group_id = int(message.command[1])
            if not await is_check_admin(client, group_id, user_id):
                await message.reply_text("You're Not Admin In That Group.")
                return
            chat = await client.get_chat(group_id)
            await db.connect_group(group_id, user_id)
            await message.reply_text(f"Linked {chat.title} to PM.")
        except:
            await message.reply_text("Invalid group ID or error occurred.")

@Client.on_message(filters.command("request") & filters.private)
async def private_request(bot, message):

    if REQST_CHANNEL is None:
        return

    reporter = str(message.from_user.id)
    mention = message.from_user.mention

    # /request Movie Name → extract text safely
    parts = message.text.split(maxsplit=1)

    if len(parts) == 1:
        return await message.reply_text("<b>🎬 Please provide the name of movie/series\n\n 📝 Examples:\n /request Eko 2025\n /request True Detective S04</b>")

    content = parts[1].strip()

    if len(content) < 3:
        return await message.reply_text(
            "<b><Request must be at least 3 characters.\n\nMovie/Series Neme:\nYear:\nLanguage:</b>"
        )

    # ✅ SAME admin buttons (same as group)
    btn = [[
        InlineKeyboardButton(
            "ꜱʜᴏᴡ ᴏᴘᴛɪᴏɴꜱ",
            callback_data=f"show_option#{reporter}"
        )
    ]]

    await bot.send_message(
        chat_id=REQST_CHANNEL,
        text=(
            f"<b>📝 ʀᴇǫᴜᴇꜱᴛ : <u>{content}</u>\n\n"
            f"📚 ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ : {mention}\n"
            f"📖 ʀᴇᴘᴏʀᴛᴇʀ ɪᴅ : {reporter}</b>"
        ),
        reply_markup=InlineKeyboardMarkup(btn)
    )

    await message.reply_text(
        "<b>✅ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ sᴜᴄᴄᴇssғᴜʟʟʏ sᴇɴᴛ ᴛᴏ ᴀᴅᴍɪɴ.\nᴋɪɴᴅʟʏ ᴡᴀɪᴛ ғᴏʀ ʀᴇᴘʟʏ.</b>"
    )

@Client.on_message((filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request")) & filters.group)
async def requests(bot, message):
    bot_id = bot.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    if REQST_CHANNEL is None or SUPPORT_CHAT_ID is None: return # Must add REQST_CHANNEL and SUPPORT_CHAT_ID to use this feature
    if message.reply_to_message and SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.reply_to_message.text
        try:
            if REQST_CHANNEL is not None:
                btn = [[
                        InlineKeyboardButton('ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('ꜱʜᴏᴡ ᴏᴘᴛɪᴏɴꜱ', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📝 ʀᴇǫᴜᴇꜱᴛ : <u>{content}</u>\n\n📚 ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ : {mention}\n📖 ʀᴇᴘᴏʀᴛᴇʀ ɪᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('ꜱʜᴏᴡ ᴏᴘᴛɪᴏɴꜱ', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📝 ʀᴇǫᴜᴇꜱᴛ : <u>{content}</u>\n\n📚 ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ : {mention}\n📖 ʀᴇᴘᴏʀᴛᴇʀ ɪᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>ʏᴏᴜ ᴍᴜꜱᴛ ᴛʏᴘᴇ ᴀʙᴏᴜᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ [ᴍɪɴɪᴍᴜᴍ 3 ᴄʜᴀʀᴀᴄᴛᴇʀꜱ]. ʀᴇǫᴜᴇꜱᴛꜱ ᴄᴀɴ'ᴛ ʙᴇ ᴇᴍᴘᴛʏ.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
        
    elif SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.text.strip()
        keywords = ["#request", "/request", "#Request", "/Request"]
        for keyword in keywords:
            if keyword in content:
                content = content.replace(keyword, "")
        try:
            if REQST_CHANNEL is not None and len(content) >= 3:
                btn = [[
                        InlineKeyboardButton('ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('ꜱʜᴏᴡ ᴏᴘᴛɪᴏɴꜱ', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📝 ʀᴇǫᴜᴇꜱᴛ : <u>{content}</u>\n\n📚 ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ : {mention}\n📖 ʀᴇᴘᴏʀᴛᴇʀ ɪᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('ꜱʜᴏᴡ ᴏᴘᴛɪᴏɴꜱ', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📝 ʀᴇǫᴜᴇꜱᴛ : <u>{content}</u>\n\n📚 ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ : {mention}\n📖 ʀᴇᴘᴏʀᴛᴇʀ ɪᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>ʏᴏᴜ ᴍᴜꜱᴛ ᴛʏᴘᴇ ᴀʙᴏᴜᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ [ᴍɪɴɪᴍᴜᴍ 3 ᴄʜᴀʀᴀᴄᴛᴇʀꜱ]. ʀᴇǫᴜᴇꜱᴛꜱ ᴄᴀɴ'ᴛ ʙᴇ ᴇᴍᴘᴛʏ.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
    
    elif SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.text
        keywords = ["#request", "/request", "#Request", "/Request"]
        for keyword in keywords:
            if keyword in content:
                content = content.replace(keyword, "")
        try:
            if REQST_CHANNEL is not None and len(content) >= 3:
                btn = [[
                        InlineKeyboardButton('ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('ꜱʜᴏᴡ ᴏᴘᴛɪᴏɴꜱ', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📝 ʀᴇǫᴜᴇꜱᴛ : <u>{content}</u>\n\n📚 ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ : {mention}\n📖 ʀᴇᴘᴏʀᴛᴇʀ ɪᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('ꜱʜᴏᴡ ᴏᴘᴛɪᴏɴꜱ', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📝 ʀᴇǫᴜᴇꜱᴛ : <u>{content}</u>\n\n📚 ʀᴇᴘᴏʀᴛᴇᴅ ʙʏ : {mention}\n📖 ʀᴇᴘᴏʀᴛᴇʀ ɪᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>ʏᴏᴜ ᴍᴜꜱᴛ ᴛʏᴘᴇ ᴀʙᴏᴜᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ [ᴍɪɴɪᴍᴜᴍ 3 ᴄʜᴀʀᴀᴄᴛᴇʀꜱ]. ʀᴇǫᴜᴇꜱᴛꜱ ᴄᴀɴ'ᴛ ʙᴇ ᴇᴍᴘᴛʏ.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
    else:
        success = False    
    if success:
        link = await bot.create_chat_invite_link(int(REQST_CHANNEL))
        btn = [[
                InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=link.invite_link),
                InlineKeyboardButton('ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ', url=f"{reported_post.link}")
              ]]
        await message.reply_text("<b>ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ʙᴇᴇɴ ᴀᴅᴅᴇᴅ! ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ ꜰᴏʀ ꜱᴏᴍᴇ ᴛɪᴍᴇ.\n\nᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ & ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn))
    
@Client.on_message(filters.command("send") & filters.user(ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>ʏᴏᴜʀ ᴍᴇꜱꜱᴀɢᴇ ʜᴀꜱ ʙᴇᴇɴ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ꜱᴇɴᴛ ᴛᴏ {user.mention}.</b>")
            else:
                await message.reply_text("<b>ᴛʜɪꜱ ᴜꜱᴇʀ ᴅɪᴅɴ'ᴛ ꜱᴛᴀʀᴛᴇᴅ ᴛʜɪꜱ ʙᴏᴛ ʏᴇᴛ !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text("<b>ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴀꜱ ᴀ ʀᴇᴘʟʏ ᴛᴏ ᴀɴʏ ᴍᴇꜱꜱᴀɢᴇ ᴜꜱɪɴɢ ᴛʜᴇ ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ ɪᴅ. ꜰᴏʀ ᴇɢ:  /send ᴜꜱᴇʀɪᴅ</b>")

@Client.on_message(filters.command("deletefiles") & filters.user(ADMINS))
async def deletemultiplefiles(bot, message):
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, This command won't work in groups. It only works on my PM !</b>")
    else:
        pass
    try:
        keyword = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, Give me a keyword along with the command to delete files.</b>")
    k = await bot.send_message(chat_id=message.chat.id, text=f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword)
    await k.delete()
    btn = [[
       InlineKeyboardButton("⚠️ Yes, Continue ! ⚠️", callback_data=f"killfilesdq#{keyword}")
       ],[
       InlineKeyboardButton("❌ No, Abort operation ! ❌", callback_data="close_data")
    ]]
    await message.reply_text(
        text=f"<b>Found {total} files for your query {keyword} !\n\nDo you want to delete?</b>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )

@Client.on_callback_query(filters.regex("topsearch"))
async def topsearch_callback(client, callback_query):    
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))    
    limit = 20  
    top_messages = await silentdb.get_top_messages(limit)
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        msg_lower = msg.lower()
        if msg_lower not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg_lower)            
            if len(msg) > 35:
                truncated_messages.append(msg[:32] + "...")
            else:
                truncated_messages.append(msg)
    keyboard = [truncated_messages[i:i+2] for i in range(0, len(truncated_messages), 2)]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        one_time_keyboard=True, 
        resize_keyboard=True, 
        placeholder="Most searches of the day"
    )
    await callback_query.message.reply_text("<b>Tᴏᴘ Sᴇᴀʀᴄʜᴇs Oғ Tʜᴇ Dᴀʏ 👇</b>", reply_markup=reply_markup)
    await callback_query.answer()

@Client.on_message(filters.command('top_search'))
async def top(_, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    try:
        limit = int(message.command[1])
    except (IndexError, ValueError):
        limit = 20
    top_messages = await silentdb.get_top_messages(limit)
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        if msg.lower() not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg.lower())            
            if len(msg) > 35:
                truncated_messages.append(msg[:35 - 3])
            else:
                truncated_messages.append(msg)
    keyboard = []
    for i in range(0, len(truncated_messages), 2):
        row = truncated_messages[i:i+2]
        keyboard.append(row)
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, placeholder="Most searches of the day")
    await message.reply_text(f"<b>Tᴏᴘ Sᴇᴀʀᴄʜᴇs Oғ Tʜᴇ Dᴀʏ 👇</b>", reply_markup=reply_markup)

    
@Client.on_message(filters.command('trendlist'))
async def trendlist(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    limit = 31
    if len(message.command) > 1:
        try:
            limit = int(message.command[1])
        except ValueError:
            await message.reply_text("Invalid number format.\nPlease provide a valid number after the /trendlist command.")
            return 
    try:
        top_messages = await silentdb.get_top_messages(limit)
    except Exception as e:
        await message.reply_text(f"Error retrieving messages: {str(e)}")
        return  
    if not top_messages:
        await message.reply_text("No top messages found.")
        return 
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        if msg.lower() not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg.lower())
            truncated_messages.append(msg[:32] + '...' if len(msg) > 35 else msg)
    if not truncated_messages:
        await message.reply_text("No valid top messages found.")
        return  
    formatted_list = "\n".join([f"{i+1}. <b>{msg}</b>" for i, msg in enumerate(truncated_messages)])
    additional_message = "⚡️ 𝑨𝒍𝒍 𝒕𝒉𝒆 𝒓𝒆𝒔𝒖𝒍𝒕𝒔 𝒂𝒃𝒐𝒗𝒆 𝒄𝒐𝒎𝒆 𝒇𝒓𝒐𝒎 𝒘𝒉𝒂𝒕 𝒖𝒔𝒆𝒓𝒔 𝒉𝒂𝒗𝒆 𝒔𝒆𝒂𝒓𝒄𝒉𝒆𝒅 𝒇𝒐𝒓. 𝑻𝒉𝒆𝒚'𝒓𝒆 𝒔𝒉𝒐𝒘𝒏 𝒕𝒐 𝒚𝒐𝒖 𝒆𝒙𝒂𝒄𝒕𝒍𝒚 𝒂𝒔 𝒕𝒉𝒆𝒚 𝒘𝒆𝒓𝒆 𝒔𝒆𝒂𝒓𝒄𝒉𝒆𝒅, 𝒘𝒊𝒕𝒉𝒐𝒖𝒕 𝒂𝒏𝒚 𝒄𝒉𝒂𝒏𝒈𝒆𝒔 𝒃𝒚 𝒕𝒉𝒆 𝒐𝒘𝒏𝒆𝒓."
    formatted_list += f"\n\n{additional_message}"
    reply_text = f"<b>Top {len(truncated_messages)} Tʀᴀɴᴅɪɴɢ ᴏғ ᴛʜᴇ ᴅᴀʏ 👇:</b>\n\n{formatted_list}"
    await message.reply_text(reply_text)

@Client.on_message(filters.private & filters.command("pm_search") & filters.user(ADMINS))
async def set_pm_search(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("<b>💔 Invalid option. Please send 'on' or 'off' after the command..</b>")
        return
    try:
        await db.update_pm_search_status(bot_id, enable_status)
        response_text = (
            "<b> ᴘᴍ ꜱᴇᴀʀᴄʜ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b> ᴘᴍ ꜱᴇᴀʀᴄʜ ᴅɪꜱᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        await log_error(client, f"Error in set_pm_search: {e}")
        await message.reply_text(f"<b>❗ An error occurred: {e}</b>")

@Client.on_message(filters.private & filters.command("movie_update") & filters.user(ADMINS))
async def set_movie_update_notification(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("<b>💔 Invalid option. Please send 'on' or 'off' after the command.</b>")
        return
    try:
        await db.update_movie_update_status(bot_id, enable_status)
        response_text = (
            "<b>ᴍᴏᴠɪᴇ ᴜᴘᴅᴀᴛᴇ ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b>ᴍᴏᴠɪᴇ ᴜᴘᴅᴀᴛᴇ ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ ᴅɪꜱᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        await log_error(client, f"Error in set_movie_update_notification: {e}")
        await message.reply_text(f"<b>❗ An error occurred: {e}</b>")

@Client.on_message(filters.private & filters.command("maintenance") & filters.user(ADMINS))
async def set_maintenance_mode(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("💔 Invalid Option. Please Send 'on' or 'off' Along With Command.. Example- /maintenance on")
        return
    try:
        await db.update_maintenance_status(bot_id, enable_status)
        response_text = (
            "<b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴅɪꜱᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        await log_error(client, f"Error in set_maintenance_mode: {e}")
        await message.reply_text(f"<b>❗ An error occurred: {e}</b>")
        

@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def stop_button(bot, message):
    msg = await bot.send_message(text="<b><i>ʙᴏᴛ ɪꜱ ʀᴇꜱᴛᴀʀᴛɪɴɢ</i></b>", chat_id=message.chat.id)       
    await asyncio.sleep(3)
    await msg.edit("<b><i><u>ʙᴏᴛ ɪꜱ ʀᴇꜱᴛᴀʀᴛᴇᴅ</u> ✅</i></b>")
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.command("reset_group"))
async def reset_group_command(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text('<b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ</b>')
    sts = await message.reply("<b>♻️ ᴄʜᴇᴄᴋɪɴɢ...</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪɴ ɢʀᴏᴜᴘ...</b>")
    btn = [[
        InlineKeyboardButton('🚫 ᴄʟᴏsᴇ 🚫', callback_data='close_data')
    ]]
    reply_markup = InlineKeyboardMarkup(btn)
    await save_group_settings(grp_id, 'shortner', SHORTENER_WEBSITE)
    await save_group_settings(grp_id, 'api', SHORTENER_API)
    await save_group_settings(grp_id, 'shortner_two', SHORTENER_WEBSITE2)
    await save_group_settings(grp_id, 'api_two', SHORTENER_API2)
    await save_group_settings(grp_id, 'shortner_three', SHORTENER_WEBSITE3)
    await save_group_settings(grp_id, 'api_three', SHORTENER_API3)
    await save_group_settings(grp_id, 'verify_time', TWO_VERIFY_GAP)
    await save_group_settings(grp_id, 'third_verify_time', THREE_VERIFY_GAP)
    await save_group_settings(grp_id, 'template', IMDB_TEMPLATE)
    await save_group_settings(grp_id, 'tutorial', TUTORIAL)
    await save_group_settings(grp_id, 'tutorial_2', TUTORIAL_2)
    await save_group_settings(grp_id, 'tutorial_3', TUTORIAL_3)
    await save_group_settings(grp_id, 'caption', CUSTOM_FILE_CAPTION)
    await save_group_settings(grp_id, 'log', LOG_VR_CHANNEL)
    await save_group_settings(grp_id, 'is_verify', IS_VERIFY)
    await save_group_settings(grp_id, 'fsub_id', AUTH_CHANNEL)
    await message.reply_text('ꜱᴜᴄᴄᴇꜱꜱғᴜʟʟʏ ʀᴇꜱᴇᴛ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ...')

@Client.on_message(filters.command('details'))
async def all_settings(client, message):    
    try:
        bot_id = client.me.id
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in ADMINS:
            await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
            return
        chat_type = message.chat.type
        if chat_type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return await message.reply_text("<b>ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪɴ ɢʀᴏᴜᴘ...</b>")
        grp_id = message.chat.id
        title = message.chat.title
        
        if not await is_check_admin(client, grp_id, message.from_user.id):
            return await message.reply_text('<b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ</b>') 
        
        settings = await get_settings(grp_id)
        nbbotz = f"""<b>⚙️ ʏᴏᴜʀ sᴇᴛᴛɪɴɢs ꜰᴏʀ - {title}</b>

✅️ <b><u>1sᴛ ᴠᴇʀɪꜰʏ sʜᴏʀᴛɴᴇʀ</u></b>
<b>ɴᴀᴍᴇ</b> - <code>{settings["shortner"]}</code>
<b>ᴀᴘɪ</b> - <code>{settings["api"]}</code>

✅️ <b><u>2ɴᴅ ᴠᴇʀɪꜰʏ sʜᴏʀᴛɴᴇʀ</u></b>
<b>ɴᴀᴍᴇ</b> - <code>{settings["shortner_two"]}</code>
<b>ᴀᴘɪ</b> - <code>{settings["api_two"]}</code>

✅️ <b><u>𝟹ʀᴅ ᴠᴇʀɪꜰʏ sʜᴏʀᴛɴᴇʀ</u></b>
<b>ɴᴀᴍᴇ</b> - <code>{settings["shortner_three"]}</code>
<b>ᴀᴘɪ</b> - <code>{settings["api_three"]}</code>

⏰ <b>2ɴᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ</b> - <code>{settings["verify_time"]}</code>

⏰ <b>𝟹ʀᴅ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴛɪᴍᴇ</b> - <code>{settings['third_verify_time']}</code>

1️⃣ <b>ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ 1</b> - {settings['tutorial']}

2️⃣ <b>ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ 2</b> - {settings.get('tutorial_2', TUTORIAL_2)}

3️⃣ <b>ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ 3</b> - {settings.get('tutorial_3', TUTORIAL_3)}

📝 <b>ʟᴏɢ ᴄʜᴀɴɴᴇʟ ɪᴅ</b> - <code>{settings['log']}</code>

🚫 ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ ɪᴅ - `{settings['fsub_id']}`

🎯 <b>ɪᴍᴅʙ ᴛᴇᴍᴘʟᴀᴛᴇ</b> - <code>{settings['template']}</code>

📂 <b>ꜰɪʟᴇ ᴄᴀᴘᴛɪᴏɴ</b> - <code>{settings['caption']}</code>

📌 <b><i>ɴᴏᴛᴇ :- ɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʀᴇꜱᴇᴛ ʏᴏᴜʀ ꜱᴇᴛᴛɪɴɢꜱ ᴊᴜꜱᴛ ꜱᴇɴᴅ <code>/reset_group</code> ᴄᴏᴍᴍᴀɴᴅ.</i></b>
"""        
        btn = [[            
            InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_data")
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        dlt=await message.reply_text(nbbotz, reply_markup=reply_markup, disable_web_page_preview=True)
        await asyncio.sleep(300)
        await dlt.delete()
    except Exception as e:
        LOGGER.error(f"Error : {e}")
        await message.reply_text(f"Error: {e}")

@Client.on_message(filters.command('group_cmd'))
async def group_commands(client, message):
    bot_id = client.me.id
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
        return
    user = message.from_user.mention
    user_id = message.from_user.id
    await message.reply_text(script.GROUP_CMD, disable_web_page_preview=True)

@Client.on_message(filters.command('admin_cmd') & filters.user(ADMINS))
async def admin_commands(client, message):
    user = message.from_user.mention
    user_id = message.from_user.id
    await message.reply_text(script.ADMIN_CMD, disable_web_page_preview=True)

@Client.on_message(filters.private & filters.command("movies"))
async def siletxbotz_list_movies(client, message):
    try:
        bot_id = client.me.id
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in ADMINS:
            await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
            return
        movies = await siletxbotz_get_movies()
        if not movies:
            return await message.reply("❌ No Recent Movies Found", parse_mode=ParseMode.HTML)       
        msg = "<b>Latest Uploads List ✅</b>\n\n"
        msg += "<b>🎬 Movies:</b>\n"
        msg += "\n".join(f"<b>{i+1}. {m}</b>" for i, m in enumerate(movies))
        await message.reply(msg[:4096], parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Error in siletxbotz_list_movies: {e}")
        await message.reply("An Error Occurred ☹️", parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("series"))
async def siletxbotz_list_series(client, message):
    try:
        bot_id = client.me.id
        maintenance_mode = await db.get_maintenance_status(bot_id)
        if maintenance_mode and message.from_user.id not in ADMINS:
            await message.reply_text(f"ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜", disable_web_page_preview=True)
            return
        series_data = await siletxbotz_get_series()
        if not series_data:
            return await message.reply("❌ No Recent Series Found", parse_mode=ParseMode.HTML)       
        msg = "<b>Latest Uploades List ✅</b>\n\n"
        msg += "<b>📺 Series:</b>\n"
        for i, (title, seasons) in enumerate(series_data.items(), 1):
            season_list = ", ".join(f"{s}" for s in seasons)
            msg += f"<b>{i}. {title} - Season {season_list}</b>\n"
        await message.reply(msg[:4096], parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Error in siletxbotz_list_series: {e}")
        await message.reply("An Error Occurred ☹️", parse_mode=ParseMode.HTML)


@Client.on_message(filters.private & filters.command("resetall") & filters.user(ADMINS))
async def reset_all_settings(client, message):
    try:
        reset_count = await db.silentx_reset_settings()
        await message.reply(
            f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ {reset_count} ɢʀᴏᴜᴘꜱ. ᴅᴇꜰᴀᴜʟᴛ ᴠᴀʟᴜᴇꜱ ᴡɪʟʟ ʙᴇ ᴜꜱᴇᴅ ✅</b>",
            quote=True
        )
    except Exception as e:
        LOGGER.error(f"Error Processing Reset All Settings Command: {str(e)}")
        await message.reply("<b>ᴇʀʀᴏʀ 🚫.oᴄᴄᴜʀʀᴇᴅ ᴡʜɪʟᴇ ᴅᴇʟᴇᴛɪɴɢ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ! ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>", quote=True)       

@Client.on_message(filters.command("dropgroups") & filters.user(ADMINS))
async def drop_groups_command(client, message):
    try:
        await db.grp.drop()
        await message.reply("The 'groups' Collection Has Been Deleted.")
    except Exception as e:
        await message.reply(f"Failed to delete collection: {e}")

@Client.on_callback_query(
    filters.regex("^(help_menu|help_rules|help_readme|about_menu|owner_info|home|close)$")
)
async def menu_callback_handler(client, query):
    data = query.data

    # -------- HELP MENU --------
    if data == "help_menu":
        buttons = [
            [
                InlineKeyboardButton("🔍 Sᴇᴀʀᴄʜ Gᴜɪᴅᴇ", callback_data="help_rules"),
                InlineKeyboardButton("❗ Dɪsᴄʟᴀɪᴍᴇʀ", callback_data="help_readme")
            ],
            [InlineKeyboardButton("Bᴀᴄᴋ", callback_data="home")]
        ]
        try:
            await query.edit_message_caption(
                caption="Hᴇʀᴇ Is Aʟʟ Aʙᴏᴜᴛ Mʏ Usɪɴɢ Tɪᴘs..",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            await query.edit_message_text(
                text="Hᴇʀᴇ Is Aʟʟ Aʙᴏᴜᴛ Mʏ Usɪɴɢ Tɪᴘs..",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    elif data == "help_rules":
        await query.answer()
        buttons = [
            [InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help_menu")]
        ]
        try:
            await query.edit_message_caption(
                caption=script.HELP_TXT,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except:
            await query.edit_message_text(
                text=script.HELP_TXT,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

    elif data == "help_readme":
        await query.answer()
        buttons = [
            [InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help_menu")]
        ]
        try:
            await query.edit_message_caption(
                    caption=script.DISCLAIMER_TXT,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
            )
        except:
            await query.edit_message_text(
                text=script.DISCLAIMER_TXT,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

    # -------- ABOUT MENU --------
    elif data == "about_menu":
        await query.answer()
        buttons = [
            [InlineKeyboardButton("Rᴇᴘᴏʀᴛ Bᴜɢs & Fᴇᴇᴅʙᴀᴄᴋ", url=SUPPORT_GRP)],
            [InlineKeyboardButton("Uᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ", url=UPDATE_CHANNEL_LNK)],
            [
                InlineKeyboardButton("Oᴡɴᴇʀ Iɴғᴏ", callback_data="owner_info"),
                InlineKeyboardButton("Cʟᴏsᴇ ", callback_data="close")
            ],[
                InlineKeyboardButton("Hᴏᴍᴇ", callback_data="home")
            ]
        ]
        text = script.ABOUT_TXT.format(temp.B_NAME, OWNER_LNK)
        try:
            await query.edit_message_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

    # -------- OWNER INFO --------
    elif data == "owner_info":
        await query.answer()
        owner_text = """<b>
┏━•❃𓊈𒆜 Oᴡɴᴇʀ Dᴇᴛᴀɪʟꜱ 𒆜𓊉❃•━┓
◈ ɴᴀᴍᴇ : Ꮪᴡᴀᴘɴᴏɴɪʟ
◈ ʜᴏʙʙʏ : ᴡᴇʙ ʟᴇᴀʀɴɪɴɢ
◈ ғʀᴏᴍ : ᴋᴏʟᴋᴀᴛᴀ
◈ ᴘᴇʀᴍᴀɴᴇɴᴛ ᴅᴍ ʟɪɴᴋ : <a href="https://t.me/Yours_Swap_bot">ʜᴇʀᴇ ɪ ᴀᴍ</a>
‿︵‿︵‿︵‿୨❤୧‿︵‿︵‿︵‿
</b>
"""
        await query.message.edit_media(
            InputMediaPhoto(
                media=random.choice(PICS),
                caption=owner_text,
                parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="about_menu")]]
            )
        )

    # -------- HOME --------
    
# -------- HOME --------
    elif data == "home":
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
        except Exception:
            await query.edit_message_text(
                text=script.START_TXT.format(
                    user=query.from_user.mention,
                    greet=gtxt
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

    # -------- CLOSE --------
    elif data == "close":
        await query.answer()
        await query.message.delete()
