import re
import io
import math
import random
import string
import aiohttp
import asyncio
import hashlib
import requests
from info import *
from utils import *
from logging_helper import LOGGER
from typing import Optional, Dict, Any
from datetime import datetime
from pyrogram import Client, filters
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

CAPTION_LANGUAGES = ["Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla", "Telugu", "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli", "Gujrati", "Korean", "Gujarati", "Spanish", "French", "German", "Chinese", "Arabic", "Portuguese", "Russian", "Japanese", "Odia", "Assamese", "Urdu"]

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

SILENTX_PREMIUM_UPDATE = """
<blockquote>🎬 𝕻ℝ𝔼𝕄𝕀𝕌𝕄 𝕄𝕆𝕍𝕀𝔼 𝕌ℙ𝔻𝔸𝕋𝔼 🎥</blockquote>

<b><u>{}</u></b> <code>#{}</code>

<code>━━━━━━━━━━━━━━━━━━</code>
<b>🔈 Audio</b>: {}
<b>📺 Format</b>: {}
<b>📀 Episodes</b>: {}

<code>━━━━━━━━━━━━━━━━━━</code>
<b>🎭 Director</b>: {}
<b>📅 Release</b>: {}
<b>⭐ IMDb</b>: {}/10 (<code>{}</code> votes)
<b>🏷️ Genres</b>: {}
<code>━━━━━━━━━━━━━━━━━━</code>

<b>⚡ Powered By @Graduate_Movies</b>
"""

SERIES_UPDATE_TEMPLATE = """
📌 <b>NEW FILES ADDED</b>

🏷 <b>Title</b> : {} #SERIES

📍 <b>Format</b> : {}
🌿 <b>Quality</b> : {}
🔊 <b>Audio</b> : {}

📅 <b>Year</b> : {}
☀ <b>Season</b> : {:02}
💎 <b>Episodes</b> : {}
"""

MOVIE_UPDATE_TEMPLATE = """
📌 <b>NEW FILES ADDED</b>

🏷 <b>Title</b> : {} #MOVIE

📍 <b>Format</b> : {}
🌿 <b>Quality</b> : {}
🔊 <b>Audio</b> : {}

📅 <b>Year</b> : {}
"""

notified_movies = set()
media_filter = filters.document | filters.video | filters.audio

CACHE = {}
CACHE_TIME = {}
CACHE_EXPIRE = 3600

PENDING_UPDATES = {}
UPDATE_DELAY = 4

def detect_pixels(text):

    if not text:
        return []

    text = text.lower()

    pixels = [
        "2160p",
        "1440p",
        "1080p",
        "720p",
        "480p",
        "360p"
    ]

    found = []

    for p in pixels:
        if p in text:
            found.append(p)

    return found

async def get_languages(text):

    if not text:
        return "Multi-Audio"

    text = text.lower()

    lang_map = {
        "hin": "Hindi",
        "hindi": "Hindi",

        "eng": "English",
        "english": "English",

        "tam": "Tamil",
        "tamil": "Tamil",

        "tel": "Telugu",
        "telugu": "Telugu",

        "mal": "Malayalam",
        "malayalam": "Malayalam",

        "kan": "Kannada",
        "kannada": "Kannada",

        "ben": "Bengali",
        "bengali": "Bengali",
        "bangla": "Bengali",

        "mar": "Marathi",
        "marathi": "Marathi",

        "pun": "Punjabi",
        "punjabi": "Punjabi",

        "guj": "Gujarati",
        "gujarati": "Gujarati",

        "urd": "Urdu",
        "urdu": "Urdu",

        "jap": "Japanese",
        "japanese": "Japanese",

        "kor": "Korean",
        "korean": "Korean",

        "chi": "Chinese",
        "chinese": "Chinese"
    }

    tokens = re.split(r'[\s\-\._]+', text)

    found = []

    for token in tokens:
        if token in lang_map:
            found.append(lang_map[token])

    if not found:
        return "Multi-Audio"

    return ", ".join(sorted(set(found)))

async def detect_format(text: str) -> str:

    if not text:
        return "HDRip"

    text = text.lower()

    for fmt in FORMAT_KEYWORDS:
        if fmt.lower() in text:
            return fmt

    return "HDRip"

def detect_episode(text):

    if not text:
        return None

    text = text.lower()

    patterns = [

        r'\bs\d{1,2}e(\d{1,3})\b',   # S01E05
        r'\be(\d{1,3})\b',           # E05
        r'\bep(\d{1,3})\b',          # EP05
        r'\bepisode[\s\-]?(\d{1,3})\b',
        r'\b\d{1,2}x(\d{1,3})\b'     # 1x05
    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if match:
            return int(match.group(1))

    return None
    
def detect_episode_range(text):

    if not text:
        return None

    text = text.lower()

    patterns = [

        r'e(\d{1,3})\s*-\s*e?(\d{1,3})',
        r'ep(\d{1,3})\s*-\s*(\d{1,3})',
        r'episode\s*(\d{1,3})\s*-\s*(\d{1,3})',

        r's\d{1,2}e(\d{1,3})\s*-\s*e?(\d{1,3})',   # S01E01-E05
        r's\d{1,2}e(\d{1,3})\s+e?(\d{1,3})',       # S01E01 E05

        r'(\d{1,2})x(\d{1,3})\s*-\s*(\d{1,2})x(\d{1,3})'

    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if match:

            start = int(match.group(1))
            end = int(match.group(2))

            if start <= end:
                return list(range(start, end + 1))

    return None

def get_cache(key):

    now = asyncio.get_event_loop().time()

    if key in CACHE_TIME:

        if now - CACHE_TIME[key] > CACHE_EXPIRE:

            CACHE.pop(key, None)
            CACHE_TIME.pop(key, None)

    if key not in CACHE:

        CACHE[key] = {
            "seasons": {},
            "combined": set(),
            "qualities": set(),
            "languages": set(),
            "message_id": None
        }

    CACHE_TIME[key] = now

    return CACHE[key]

def schedule_update(bot, key, caption, tmdb):

    if key in PENDING_UPDATES:
        PENDING_UPDATES[key].cancel()

    loop = asyncio.get_event_loop()

    PENDING_UPDATES[key] = loop.call_later(
        UPDATE_DELAY,
        lambda: asyncio.create_task(send_with_visual(bot, caption, tmdb, key))
    )

def is_combined(text):

    if not text:
        return False

    text = text.lower()

    keywords = [
        "combined",
        "complete",
        "full season",
        "all episodes"
    ]

    for word in keywords:
        if word in text:
            return True

    return False

def build_episode_range(episodes):

    if not episodes:
        return None

    eps = sorted(set(episodes))

    start = eps[0]
    prev = eps[0]

    ranges = []

    for ep in eps[1:]:

        if ep == prev + 1:
            prev = ep
            continue

        if start == prev:
            ranges.append(f"E{start:02}")
        else:
            ranges.append(f"E{start:02}-E{prev:02}")

        start = ep
        prev = ep

    if start == prev:
        ranges.append(f"E{start:02}")
    else:
        ranges.append(f"E{start:02}-E{prev:02}")

    return ", ".join(ranges)

def build_season_text(seasons, combined):

    lines = []

    all_seasons = set(seasons.keys()) | set(combined)

    for season in sorted(all_seasons):

        eps = seasons.get(season, set())

        ep_text = build_episode_range(eps)

        if season in combined:

            if ep_text:
                lines.append(f"☀ <b>Season {season:02}</b> : {ep_text} + COMBINED")
            else:
                lines.append(f"☀ <b>Season {season:02}</b> : COMBINED")

        else:

            if ep_text:
                lines.append(f"☀ <b>Season {season:02}</b> : {ep_text}")

    return "\n".join(lines)

def detect_season(text):

    if not text:
        return None

    text = text.lower()

    patterns = [
        r's(\d{1,2})',
        r'season[\s\-]?(\d{1,2})'
    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if match:
            return int(match.group(1))

    return None

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media is not None:
            break
    else:
        return
    media.file_type = file_type
    media.caption = message.caption or ""
    success, silentxbotz = await save_file(media)
    try:  
        if success and silentxbotz == 1 and await get_status(bot.me.id):            
            await send_movie_update(bot, file_name=media.file_name, caption=media.caption)
    except Exception as e:
        LOGGER.error(f"Error In Movie Update - {e}")
        pass

async def send_movie_update(bot, file_name, caption):
    try:

        file_name = await movie_name_format(file_name)        
        caption = caption or ""

        year_match = re.search(r"(19|20)\d{2}", f"{file_name} {caption}")
        year = year_match.group(0) if year_match else None

        episode = detect_episode(f"{file_name} {caption}")
        episode_range = detect_episode_range(f"{file_name} {caption}")
        combined = is_combined(f"{file_name} {caption}")

        quality = await get_qualities(caption) or "HDRip"
        pixels = detect_pixels(f"{file_name} {caption}")
        pixel = ", ".join(pixels) if pixels else "720p"
        language = await get_languages(caption) or "Multi-Audio"

        season_match = re.search(r"(?i)(?:s|season)0*(\d{1,2})", caption) or re.search(r"(?i)(?:s|season)0*(\d{1,2})", file_name)

        if year:
            file_name = file_name[:file_name.find(year) + 4]

        elif season_match:
            season = season_match.group(1)
            file_name = file_name[:file_name.find(season) + 1]

        # cache
        cache = get_cache(file_name)

        # episode store
        season = detect_season(f"{file_name} {caption}")

        if season:

            if season not in cache["seasons"]:
                cache["seasons"][season] = set()

            if episode is not None:
                cache["seasons"][season].add(int(episode))

            if episode_range:
                for ep in episode_range:
                    cache["seasons"][season].add(int(ep))

            if combined:
                cache["combined"].add(season)

        # quality store
        if pixels:
            for p in pixels:
                cache["qualities"].add(p.strip())

        # language store
        if language:
            for l in language.split(","):
                cache["languages"].add(l.strip())

        fmt = await detect_format(f"{file_name} {caption}")

        tmdb_data = await fetch_tmdb_data(file_name, year)

        if not tmdb_data:

            basic_title = file_name.replace(".", " ").strip()

            if year:
                basic_title = f"{basic_title} {year}"

            caption = MOVIE_UPDATE_TEMPLATE.format(
                basic_title,
                fmt,
                quality_text,
                lang_text,
                year or "N/A"
            )

            # safe fallback data
            tmdb_data = {
                "title": basic_title,
                "release_date": "",
                "poster_url": "",
                "backdrop_url": ""
            }

            schedule_update(bot, cache_key, caption, tmdb_data)
            return

        quality_text = ", ".join(sorted(cache["qualities"])) or pixel
        lang_text = ", ".join(sorted(cache["languages"])) or language

        is_series = "tv" in tmdb_data.get("kind","").lower() or cache["seasons"]

        year_text = tmdb_data.get("release_date","")
        year_text = year_text[:4] if year_text else "N/A"

        search_movie = file_name.replace(" ", "-")

        season_num = None

        if cache["seasons"]:
            season_num = max(cache["seasons"].keys())

        title_display = escape_html(tmdb_data["title"])

        # title পাশে season / year শুধু caption বা filename থেকে
        if is_series and season_num:
            title_display = f"{title_display} S{season_num:02}"

        elif not is_series and year:
            title_display = f"{title_display} {year}"
        
        episodes = cache["seasons"].get(season_num, set())
        episode_text = build_episode_range(episodes)

        if season_num and season_num in cache["combined"]:
            if episode_text:
                episode_text = f"{episode_text} + COMBINED"
            else:
                episode_text = "COMBINED"

        if is_series and season_num:

            full_caption = SERIES_UPDATE_TEMPLATE.format(
                title_display,
                fmt,
                quality_text,
                lang_text,
                year_text,
                season_num,
                episode_text or "N/A"
            )

        else:

            full_caption = MOVIE_UPDATE_TEMPLATE.format(
                title_display,
                fmt,
                quality_text,
                lang_text,
                year_text,
            )

        schedule_update(bot, file_name, full_caption, tmdb_data)

    except Exception as e:
        LOGGER.error(f"Error In Movie Update: {e}")

        
def escape_html(text: str) -> str:
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def fetch_tmdb_data(title: str, year: str = None) -> Optional[Dict[str, Any]]:
    base_url = "https://image.silentxbotz.tech/api/v2/poster"
    params = {"title": title.strip()}
    if year:
        params["year"] = year
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params, timeout=aiohttp.ClientTimeout(total=25)) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                
                return {
                    "id": data.get("id"),
                    "title": data.get("title", title),
                    "original_title": data.get("original_title", ""),
                    "kind": data.get("type", "Movie").upper(),
                    "director": await get_director_from_crew(data.get("crew", [])),
                    "release_date": data.get("release_date", ""),
                    "vote_average": f"{data['vote_average']:.1f}" if data.get("vote_average") else "N/A",
                    "vote_count": f"{data['vote_count']:,}" if data.get("vote_count") else "0",
                    "genres": data.get("genres", []),
                    "imdb_id": data.get("imdb_id", ""),
                    "imdb_url": f"https://www.imdb.com/title/{data.get('imdb_id')}/" if data.get("imdb_id") else "",
                    "overview": data.get("overview", ""),
                    "poster_url": data.get("poster_url", ""),
                    "backdrop_url": data.get("backdrop_url", ""),
                    "backdrops": data.get("backdrops", {}),
                    "posters": data.get("posters", {}),
                    "cast": data.get("cast", [])[:5],
                    "videos": data.get("videos", []),
                }
                
    except Exception as e:
        LOGGER.error(f"API Fetch Error: {str(e)}")
        return None

async def get_director_from_crew(crew: list) -> str:
    directors = [person["name"] for person in crew if person.get("job") == "Director"]
    return directors[0] if directors else None

def get_trailer_button(tmdb_data: Dict) -> list:
    videos = tmdb_data.get("videos", [])
    yt_videos = [v for v in videos if "youtube" in v.get("url", "").lower()]    
    if yt_videos:
        return [InlineKeyboardButton("▶️ Watch Trailer", url=yt_videos[0]["url"])]
    return []
    
async def send_with_visual(bot, caption, tmdb_data, key):

    try:

        cache = get_cache(key)

        visual_url = None
        if tmdb_data:
            visual_url = await get_best_visual(tmdb_data)

        get_file = f'https://telegram.me/{temp.U_NAME}?start=getfile-{key.replace(" ","-")}'

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❗ ᴄʟɪᴄᴋ ᴛᴏ ɢᴇᴛ ғɪʟᴇ ❗", url=get_file)],
            get_trailer_button(tmdb_data)
        ])

        photo_to_send = DEFAULT_IMAGE_URL

        if visual_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(visual_url, timeout=aiohttp.ClientTimeout(total=20)) as img_resp:

                        if img_resp.status == 200:

                            img_bytes = await img_resp.read()

                            photo_file = io.BytesIO(img_bytes)

                            photo_file.name = await generate_premium_filename(tmdb_data["title"])

                            photo_to_send = photo_file

            except:
                pass


        # FIRST MESSAGE
        if cache["message_id"] is None:

            msg = await bot.send_photo(
                chat_id=MOVIE_UPDATE_CHANNEL,
                photo=photo_to_send,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

            cache["message_id"] = msg.id


        # EDIT MESSAGE
        else:

            try:

                await bot.edit_message_caption(
                    MOVIE_UPDATE_CHANNEL,
                    cache["message_id"],
                    caption,
                    reply_markup=keyboard
                )

            except Exception as e:

                LOGGER.error(f"Edit Error: {e}")

    except Exception as e:

        LOGGER.error(f"Visual Send Error: {e}")

async def get_best_visual(tmdb_data: Dict) -> Optional[str]:
    backdrops = tmdb_data.get("backdrops", {})
    posters = tmdb_data.get("posters", {})    
    by_language = backdrops.get("by_language", {})    
    original_lang = tmdb_data.get("original_language")
    if original_lang and by_language.get(original_lang):
        return by_language[original_lang][0]["url"]    
    indian_langs = [
        "hi", "ta", "te", "kn", "ml", "mr", "bn", "gu", "pa", "or", "as", 
        "ur", "ne"
    ]
    for lang in indian_langs:
        if by_language.get(lang):
            return by_language[lang][0]["url"]    
    if by_language.get("en"):
        return by_language["en"][0]["url"]
    if by_language.get("unknown"):
        return by_language["unknown"][0]["url"]    
    if backdrops.get("all") and backdrops["all"]:
        return backdrops["all"][0]["url"]
    if posters.get("all") and posters["all"]:
        return posters["all"][0]["url"]
    if tmdb_data.get("poster_url"):
        return tmdb_data["poster_url"]           
    return None

async def generate_premium_filename(title: str, extension=".jpg") -> str:
    clean_title = re.sub(r'[^\w\s-]', '', title)[:20].strip()
    timestamp = datetime.now().strftime("%y%m%d%H%M")
    unique_id = hashlib.md5(title.encode()).hexdigest()[:6]
    return f"silentx_{clean_title}_{timestamp}_{unique_id}{extension}"

async def get_languages(text: str) -> str:
    found_langs = [lang for lang in CAPTION_LANGUAGES if lang.lower().replace(" ", "") in text.lower().replace(" ", "")]
    return ", ".join(found_langs[:2]) if found_langs else "Multi-Audio"

async def get_qualities(text): 
    qualities = ["ORG", "org", "hdcam", "HDCAM", "HQ", "hq", "HDRip", "hdrip", "camrip", "WEB-DL", "CAMRip", "hdtc", "predvd", "DVDscr", "dvdscr", "dvdrip", "HDTC", "dvdscreen", "HDTS", "hdts"]
    return ", ".join([q for q in qualities if q.lower() in text.lower()])

async def get_pixels(caption):
    pixels = ["480p", "480p HEVC", "720p", "720p HEVC", "1080p", "1080p HEVC", "2160p", "2K", "4K"]
    return ", ".join([p for p in pixels if p.lower() in caption.lower()])

async def movie_name_format(file_name):
    clean_filename = re.sub(r'http\S+', '', re.sub(r'@\w+|#\w+', '', file_name).replace('_', ' ').replace('[', '').replace(']', '').replace('(', '').replace(')', '').replace('{', '').replace('}', '').replace('.', ' ').replace('@', '').replace(':', '').replace(';', '').replace("'", '').replace('-', '').replace('!', '')).strip()
    return clean_filename
