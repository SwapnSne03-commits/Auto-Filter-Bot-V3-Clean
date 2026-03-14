import re
import io
import aiohttp
import asyncio
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

from info import *
from utils import *
from logging_helper import LOGGER

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from database.ia_filterdb import save_file

CAPTION_LANGUAGES = [
    "Bhojpuri","Hindi","Bengali","Tamil","English","Bangla","Telugu",
    "Malayalam","Kannada","Marathi","Punjabi","Gujarati","Korean",
    "Spanish","French","German","Chinese","Arabic","Portuguese",
    "Russian","Japanese","Odia","Assamese","Urdu"
]

FORMAT_KEYWORDS = [
    "WEB-DL",
    "WEBRip",
    "HDRip",
    "BluRay",
    "BRRip",
    "BDRip",
    "CAMRip",
    "HDCAM",
    "HDTC",
    "DVDRip",
    "DVDScr",
    "PreDVD",
    "HQ"
]

DEFAULT_IMAGE_URL = "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

media_filter = filters.document | filters.video | filters.audio


# ------------------------------------------------
# SMART CACHE SYSTEM
# ------------------------------------------------

CACHE = {}
PENDING_UPDATES = {}
UPDATE_DELAY = 4

def schedule_update(bot, key, caption, tmdb):

    if key in PENDING_UPDATES:

        PENDING_UPDATES[key].cancel()

    loop = asyncio.get_event_loop()

    PENDING_UPDATES[key] = loop.call_later(
        UPDATE_DELAY,
        lambda: asyncio.create_task(send_with_visual(bot, caption, tmdb, key))
    )

def get_cache(key):

    if key not in CACHE:

        CACHE[key] = {
            "qualities": set(),
            "languages": set(),
            "seasons": {},
            "message_id": None
        }

    return CACHE[key]

def detect_format(text):

    for fmt in FORMAT_KEYWORDS:

        if fmt.lower() in text.lower():

            return fmt

    return "WEBRip"

def add_episode(cache, season, episode, combined):

    if season not in cache["seasons"]:

        cache["seasons"][season] = {
            "episodes": set(),
            "combined": False
        }

    season_data = cache["seasons"][season]

    if combined:

        season_data["combined"] = True

        if episode:
            season_data["episodes"].add(episode)

        return

    if episode:

        season_data["episodes"].add(episode)

def build_season_text(seasons):

    lines = []

    for season in sorted(seasons.keys()):

        data = seasons[season]

        if data["combined"]:

            if data["episodes"]:

                ep_text = build_episode_range(data["episodes"])

            else:

                ep_text = "COMBINED"
        else:

            ep_text = build_episode_range(data["episodes"])

        lines.append(f"☀ <b>Season</b> : {season}\n💎 <b>Episodes</b> : {ep_text}")

    return "\n".join(lines)

# ------------------------------------------------
# EPISODE DETECT
# ------------------------------------------------

def detect_episode(text):

    text = text.lower()

    patterns = [

        r'e(\d{1,3})',          # E01
        r'ep(\d{1,3})',         # Ep01
        r'episode[\s\-]?(\d{1,3})', # Episode 01
        r'(\d{1,2})x(\d{1,3})'  # 1x01
    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if match:

            if 'x' in pattern:

                return int(match.group(2))

            return int(match.group(1))

    return None

def detect_episode_range(text):

    text = text.lower()

    patterns = [

        r'e(\d{1,3})\s*-\s*e?(\d{1,3})',
        r'ep(\d{1,3})\s*-\s*(\d{1,3})',
        r'episode\s*(\d{1,3})\s*-\s*(\d{1,3})',
        r'(\d{1,2})x(\d{1,3})\s*-\s*(\d{1,2})x(\d{1,3})'
    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if match:

            start = int(match.group(1))
            end = int(match.group(2))

            return list(range(start, end + 1))

    return None

def detect_season(text):

    match = re.search(r"S(\d{1,2})", text, re.I)

    if match:
        return match.group(1)

    return None


def is_combined(text):

    text = text.lower()

    if "combined" in text or "complete" in text:
        return True

    return False


def build_episode_range(episodes):

    if not episodes:
        return None

    eps = sorted(set(episodes))

    ranges = []

    start = eps[0]
    end = eps[0]

    for num in eps[1:]:

        if num == end + 1:

            end = num

        else:

            if start == end:
                ranges.append(f"E{start:02}")
            else:
                ranges.append(f"E{start:02}-E{end:02}")

            start = end = num

    if start == end:
        ranges.append(f"E{start:02}")
    else:
        ranges.append(f"E{start:02}-E{end:02}")

    return ", ".join(ranges)


# ------------------------------------------------
# QUALITY DETECT
# ------------------------------------------------

def detect_pixels(text):

    pixels = ["480p","720p","1080p","2160p"]

    found = []

    for p in pixels:
        if p.lower() in text.lower():
            found.append(p)

    return found


# ------------------------------------------------
# LANGUAGE DETECT
# ------------------------------------------------

def detect_languages(text):

    found = []

    for lang in CAPTION_LANGUAGES:
        if lang.lower() in text.lower():
            found.append(lang)

    if not found:
        return ["Multi-Audio"]

    return found


# ------------------------------------------------
# CLEAN FILENAME
# ------------------------------------------------

async def movie_name_format(file_name):

    if not file_name:
        return ""

    clean = re.sub(r'http\S+','',file_name)

    clean = re.sub(r'@\w+|#\w+','',clean)

    clean = clean.replace('_',' ').replace('.',' ')

    clean = clean.replace('[','').replace(']','')

    clean = clean.replace('(','').replace(')','')

    clean = clean.replace('{','').replace('}','')

    clean = clean.replace(':','').replace(';','')

    clean = clean.replace("'",'')

    clean = clean.replace('-',' ')

    return re.sub(r'\s+',' ',clean).strip()


# ------------------------------------------------
# TMDB FETCH
# ------------------------------------------------

async def fetch_tmdb_data(title: str, year: str=None) -> Optional[Dict[str, Any]]:

    url = "https://image.silentxbotz.tech/api/v2/poster"

    params = {"title":title}

    if year:
        params["year"] = year

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(url,params=params) as r:

                if r.status != 200:
                    return None

                return await r.json()

    except Exception as e:

        LOGGER.error(e)

        return None

async def send_with_visual(bot, caption, tmdb, key):

    cache = CACHE[key]

    poster = tmdb.get("poster_url") or DEFAULT_IMAGE_URL

    button = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "📱 Get File",
            url=f"https://t.me/{temp.U_NAME}?start=getfile-{key.replace(' ','-')}"
        )]]
    )

    if cache["message_id"] is None:

        msg = await bot.send_photo(
            chat_id=MOVIE_UPDATE_CHANNEL,
            photo=poster,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=button
        )

        cache["message_id"] = msg.id

    else:

        try:

            await bot.edit_message_caption(
                MOVIE_UPDATE_CHANNEL,
                cache["message_id"],
                caption,
                reply_markup=button
            )

        except:
            pass


async def send_movie_update(bot, file_name, caption):

    try:

        text = f"{file_name} {caption}"

        file_name = await movie_name_format(file_name)

        year_match = re.search(r"\b(19|20)\d{2}\b", text)

        year = year_match.group(0) if year_match else None

        season = detect_season(text)

        episode = detect_episode(text)

        episode_range = detect_episode_range(text)

        combined = is_combined(text)

        qualities = detect_pixels(text)

        languages = detect_languages(text)

        fmt = detect_format(text)

        cache = get_cache(file_name)

        if season:
            cache["season"] = season

        for q in qualities:

            if q not in cache["qualities"]:

                cache["qualities"].add(q)

        if season:

            if episode_range:

                for ep in episode_range:
                    if ep not in cache["seasons"].get(season, {}).get("episodes", set()):
                        add_episode(cache, season, ep, combined)

            elif episode:

                if episode not in cache["seasons"].get(season, {}).get("episodes", set()):

                    add_episode(cache, season, episode, combined)

            if combined:

                add_episode(cache, season, None, combined)

        tmdb = await fetch_tmdb_data(file_name,year)

        if not tmdb:
            return

        quality_text = ", ".join(sorted(cache["qualities"])) or "720p"

        cache["languages"].update(languages)
        lang_text = ", ".join(sorted(cache["languages"]))
        season_text = build_season_text(cache["seasons"])

        if season:

            caption_text = f"""
📢 <b>NEW FILES ADDED</b>

🏷 <b>Title</b> : {tmdb.get("title", file_name)} #SERIES

📌 <b>Format</b> : {fmt}
🍃 <b>Quality</b> : {quality_text}
🔊 <b>Audio</b> : {lang_text}

☀{season_text}
"""

        else:

            caption_text = f"""
📢 <b>NEW FILES ADDED</b>

🏷 <b>Title</b> : {tmdb.get("title", file_name)} #MOVIE

📌 <b>Format</b> : {fmt}
🍃 <b>Quality</b> : {quality_text}
🔊 <b>Audio</b> : {lang_text}
"""

        schedule_update(bot, file_name, caption_text, tmdb)

    except Exception as e:

        LOGGER.error(e)


@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):

    for t in ("document","video","audio"):

        media = getattr(message,t,None)

        if media:
            break

    if not media:
        return

    media.file_type = t

    media.caption = message.caption or ""

    success, silentxbotz = await save_file(media)

    if success and silentxbotz == 1 and await get_status(bot.me.id):

        await send_movie_update(
            bot,
            media.file_name,
            media.caption
        )

