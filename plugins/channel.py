import re
import time
import asyncio
import aiohttp
import io
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from info import *
from utils import *
from logging_helper import LOGGER
from database.ia_filterdb import save_file

# temporary notification cache
NOTIFIED_CACHE = {}

# cache lifetime (seconds)
CACHE_TIMEOUT = 86400  # 24 hours

media_filter = filters.document | filters.video | filters.audio

CAPTION_LANGUAGES = ["Bhojpuri", "Hindi", "Bengali", "Tamil", "English", "Bangla", "Telugu", "Malayalam", "Kannada", "Marathi", "Punjabi", "Bengoli", "Gujrati", "Korean", "Gujarati", "Spanish", "French", "German", "Chinese", "Arabic", "Portuguese", "Russian", "Japanese", "Odia", "Assamese", "Urdu"]

DEFAULT_IMAGE_URL = "https://te.legra.ph/file/88d845b4f8a024a71465d.jpg"

SILENTX_PREMIUM_UPDATE = """
<blockquote>🎬 𝕻ℝ𝔼𝕄𝕀𝕌𝕄 𝕄𝕆𝕍𝕀𝔼 𝕌ℙ𝔻𝔸𝕋𝔼 🎥</blockquote>

<b><u>{}</u></b> <code>#{}</code>

<code>━━━━━━━━━━━━━━━━━━</code>
<b>🔈 Audio</b>: {}
<b>📺 Format</b>: {}

<code>━━━━━━━━━━━━━━━━━━</code>
<b>🎭 Director</b>: {}
<b>📅 Release</b>: {}
<b>⭐ IMDb</b>: {}/10 (<code>{}</code> votes)
<b>🏷️ Genres</b>: {}
<code>━━━━━━━━━━━━━━━━━━</code>

<b>⚡ Powered By @Graduate_Movies</b>
"""
UPDATE_TEMPLATE = """
✅ <b>{}</b> <code>{}</code>

🎙 {}
"""

notified_movies = set()
#media_filter = filters.document | filters.video | filters.audio

COMBINED_KEYWORDS = [
    "complete",
    "complete series",
    "complete season",
    "full series",
    "season pack",
    "complete bengali series",
    "complete Bangladeshi series",
    "complete English series",
    "batch",
    "combined",
    "all episodes",
    "multi episode",
    "collection",
    "episode pack"
]

LANGUAGES = {
    "hindi":"Hindi",
    "eng":"English",
    "english":"English",
    "tam":"Tamil",
    "tamil":"Tamil",
    "tel":"Telugu",
    "telugu":"Telugu",
    "mal":"Malayalam",
    "malayalam":"Malayalam",
    "kan":"Kannada",
    "kannada":"Kannada",
    "mar":"Marathi",
    "marathi":"Marathi",
    "pun":"Punjabi",
    "punjabi":"Punjabi",
    "Panjabi":"Punjabi",
    "ben":"Bengali",
    "bangla":"Bengali",
    "bengali":"Bengali",
    "bangla":"Bangla",
    "guj":"Gujarati",
    "gujarati":"Gujarati",
    "korean":"Korean",
    "jap":"Japanese",
    "japanese":"Japanese",
    "chi":"Chinese",
    "chinese":"Chinese",
    "spanish":"Spanish",
    "french":"French",
    "german":"German",
    "russian":"Russian",
    "thai":"Thai",
    "arabic":"Arabic",
}

def clean_cache():

    now = datetime.now().timestamp()

    expired = []

    for key, ts in NOTIFIED_CACHE.items():

        if now - ts > CACHE_TIMEOUT:
            expired.append(key)

    for key in expired:
        del NOTIFIED_CACHE[key]


def save_notification(key):

    NOTIFIED_CACHE[key] = datetime.now().timestamp()

def normalize_cache_title(title: str):

    title = title.lower()

    # remove languages
    title = re.sub(r'\b(hindi|english|tamil|telugu|bengali|bangla)\b', '', title)

    # remove extra spaces
    title = re.sub(r'\s+', ' ', title).strip()

    return title

def clean_title(name: str) -> str:

    if not name:
        return ""

    original = name
    name = name.lower()

    # remove urls & tags
    name = re.sub(r'http\S+', '', name)
    name = re.sub(r'@\w+', '', name)

    # remove brackets but keep year
    name = re.sub(r'\[(.*?)\]', '', name)
    name = re.sub(r'\{(.*?)\}', '', name)

    # keep year but remove other bracket noise
    name = re.sub(r'\(([^)]*)\)', lambda m: m.group(1) if re.search(r'(19|20)\d{2}', m.group(1)) else '', name)

    # remove extension
    name = re.sub(r'\.(mkv|mp4|avi|webm)$', '', name)

    # normalize separators
    name = name.replace(".", " ").replace("_", " ").replace("-", " ")

    name = re.sub(r'\b\d+p\d*\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\b\d+fps\b', '', name, flags=re.IGNORECASE)

    name = re.sub(r'\b\d{3,}\b', '', name)
    name = re.sub(r'\b\d+(mb|gb)\b', '', name, flags=re.IGNORECASE)

    words = name.split()

    stop_words = {
        "480p","720p","1080p","1440p","2160p","360p",
        "bluray","bdrip","webrip","web","webdl","web-dl","hdrip","dvdrip",
        "x264","x265","hevc","h264","h265",
        "aac","ddp","atmos","dts",
        "dual","multi","org",
        "hindi","english","tamil","telugu","malayalam","kannada","bengali","bangla",
        "camrip","hdts","hdtc","predvd","dvd","tc","ts",
        "mkv","mp4","avi",
        "hq","nf","amzn","dsnp",
        "proper","extended","uncut","remastered"
    }

    title_words = []
    year = None

    i = 0
    while i < len(words):

        word = words[i]

        # skip resolution at beginning
        if not title_words and word in {"480p","720p","1080p","2160p"}:
            i += 1
            continue

        # 🎯 detect & stop at year
        if re.fullmatch(r'(19|20)\d{2}', word):
            year = word
            title_words.append(word)
            break

        # 🔥 NEW (resolution pattern)
        if re.match(r'\d{3,4}p\d*', word):
           break

        # 🔥 NEW (fps pattern)
        if re.match(r'\d+fps', word):
            break

        # ✅ language skip (DO NOT BREAK)
        if word in {
            "hindi","english","tamil","telugu",
            "malayalam","kannada","bengali","bangla"
        }:
            i += 1
            continue

        # 🎯 stop noisy encoding numbers
        if word.isdigit() and len(title_words) >= 2:
            break

        # 🎯 skip anime/series season prefix
        if word in {"so","s","season"} and i+1 < len(words):
            if words[i+1].isdigit():
                i += 2
                continue

        # 🎯 skip episode markers (E01 / EP01)
        if re.match(r'(e|ep)\d+', word):
            break

        # 🎯 skip "part", "vol"
        if word in {"part","vol","volume"}:
            break

        # 🎯 stop at release info
        if word in stop_words:
            break

        title_words.append(word)
        i += 1

    title = " ".join(title_words)
    title = re.sub(r'\s+', ' ', title).strip()

    title = re.sub(r'\b(hindi|english|tamil|telugu|bengali|bangla)\b', '', title, flags=re.IGNORECASE)

    title = re.sub(r'\b\d+p\d*\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\b\d+fps\b', '', title, flags=re.IGNORECASE)

    title = re.sub(r'\s+', ' ', title).strip()
    title = title.strip(" ,.-")

    # 🔥 fallback (VERY IMPORTANT)
    if not title or title in {"mkv","mp4","avi"}:

        fallback = original.lower()

        fallback = re.sub(r'\.(mkv|mp4|avi|webm)$', '', fallback)
        fallback = re.sub(r'\b(480p|720p|1080p|1440p|2160p|360p)\b', '', fallback)
        fallback = re.sub(r'\b(x264|x265|hevc|h264|h265)\b', '', fallback)
        fallback = re.sub(r'\b(bluray|bdrip|webrip|web-dl|hdrip|dvdrip)\b', '', fallback)
        fallback = re.sub(r'\b(dual|multi|aac|ddp|atmos|dts)\b', '', fallback)

        fallback = re.sub(r'\s+', ' ', fallback).strip()

        return fallback.title()

    return title.title()

def extract_title(name: str):

    if not name:
        return ""

    name = name.lower()

    # replace separators
    name = name.replace(".", " ")
    name = name.replace("_", " ")
    name = name.replace("-", " ")

    # remove urls / tags
    name = re.sub(r'http\S+', '', name)
    name = re.sub(r'@\w+', '', name)

    # remove brackets
    name = re.sub(r'\[.*?\]|\(.*?\)|\{.*?\}', '', name)

    # stop words (video info)
    stop_words = [
        "2160p","1440p","1080p","720p","480p","360p",
        "x264","x265","hevc","h264","h265",
        "webdl","webrip","bluray","hdrip","dvdrip",
        "nf","amzn","dsnp","hdtv",
        "aac","ddp","ddp5","atmos"
    ]

    parts = name.split()

    title_parts = []

    for part in parts:

        # stop if resolution etc appears
        if part in stop_words:
            break

        # stop if year
        if re.match(r'(19|20)\d{2}', part):
            break

        # stop if season
        if re.match(r's\d{1,2}', part):
            break

        title_parts.append(part)

    title = " ".join(title_parts)

    return title.strip().title()

def detect_season(text: str):

    if not text:
        return None

    text = text.lower()

    patterns = [

        r'\bs(?:eason)?[\s._-]*(\d{1,2})\b',   # S01 / Season 1
        r'\b(\d{1,2})x(\d{1,2})\b',            # 1x01
        r'\bs(\d{1,2})e\d{1,2}\b',             # S01E02
        r'\bseason[\s._-]*(\d{1,2})\b'         # Season 1

    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if match:
            return int(match.group(1))

    return None   

def detect_year(text: str):

    if not text:
        return None

    match = re.search(r'(19|20)\d{2}', text)

    if match:
        return match.group(0)

    return None

async def detect_languages(text: str):

    if not text:
        return None

    text = text.lower()

    # normalize separators
    text = re.sub(r'[\[\]\(\)\{\}\+\|/]', ' ', text)

    words = re.split(r'[\s,._\-]+', text)

    found = []

    for word in words:

        if word in LANGUAGES:

            lang = LANGUAGES[word]

            if lang not in found:
                found.append(lang)

    # Dual / Multi detection
    if not found:

        if "dual" in text:
            return "Dual Audio"

        if "multi" in text:
            return "Multi Audio"

        return None

    return ", ".join(found)

def detect_combined(text: str):

    if not text:
        return False

    text = text.lower()

    for word in COMBINED_KEYWORDS:
        if word in text:
            return True

    return False

def detect_hall_print(text: str):

    if not text:
        return False

    text = text.lower()

    hall_words = [
        "hdtc",
        "hdts",
        "hd cam"
        "hdcam",
        "camrip",
        "cam",
        "predvd",
        "pre dvd",
        "predvdrip",
        "pre dvdrip",
        "pre dvd rip"
        "hdcam",
        "telecine"
    ]

    for word in hall_words:
        if word in text:
            return True

    return False

def build_cache_key(title, season=None, year=None):

    title = normalize_cache_title(title)

    if season:
        return f"{title}_s{season}"

    if year:
        return f"{title}_{year}"

    return title

def is_already_notified(key):

    clean_cache()

    return key in NOTIFIED_CACHE

async def build_caption(title, season=None, year=None, languages=None, combined=False, hall_print=False):

    MAX_TITLE = 60

    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE].rstrip() + "..."

    # SERIES
    if season:

        if combined:
            title_text = f"{title} S{season:02} - COMBINED"
        else:
            title_text = f"{title} S{season:02}"

        tag = "#SERIES"

    else:

        if year:
            title_text = f"{title} {year}"
        else:
            title_text = title

        tag = "#MOVIE"

    caption = f"<b>✅ {title_text} {tag}</b>"

    if hall_print:
        caption += f"\n\n<blockquote><b>📸 Hall Print</b></blockquote>"

    if languages:
        caption += f"\n\n<blockquote><b>🎙 {languages}</b></blockquote>"

    links = await build_search_links(title, season)

    if links:
        caption += f"\n\n<b>{links}</b>"

    return caption

async def build_search_links(title: str, season=None):

    if not title:
        return ""

    imdb = title.replace(" ", "+")
    tmdb = title.replace(" ", "%20")
    lb = title.replace(" ", "-").lower()

    # remove year for plex slug
    plex = re.sub(r'\b(19|20)\d{2}\b', '', title).strip().replace(" ", "-").lower()

    imdb_url = f"https://www.imdb.com/find?q={imdb}"
    tmdb_url = f"https://www.themoviedb.org/search?query={tmdb}"
    lb_url = f"https://letterboxd.com/search/{lb}/"

    # Plex condition
    if season:
        plex_url = f"https://watch.plex.tv/en-GB/show/{plex}"
    else:
        plex_url = f"https://watch.plex.tv/en-GB/movie/{plex}"

    links = (
        f'⭐ <a href="{imdb_url}">IMDb</a> | '
        f'🎭 <a href="{tmdb_url}">TMDB</a> | '
        f'🟢 <a href="{lb_url}">Letterboxd</a> | '
        f'🍿 <a href="{plex_url}">Plex</a>'
    )

    return links

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):

    try:

        media = None

        if message.document:
            media = message.document

        elif message.video:
            media = message.video

        elif message.audio:
            media = message.audio

        if not media:
            return

        media.file_type = "document"

        if message.video:
            media.file_type = "video"

        if message.audio:
            media.file_type = "audio"

        media.caption = message.caption

        success, silentxbotz = await save_file(media)

        if success and silentxbotz == 1 and await get_status(bot.me.id):

            file_name = media.file_name or ""
            caption = message.caption or ""

            await send_movie_update(bot, file_name, caption)

    except Exception as e:
        LOGGER.error(f"Media Handler Error: {e}")

async def send_movie_update(bot, file_name, caption):

    try:

        caption = caption or ""
        text = f"{file_name} {caption}"

        # CLEAN TITLE (caption priority)
        source_text = caption if caption else file_name
        title = extract_title(source_text)

        # prevent bad titles
        if not title or title.lower() in {"mkv", "mp4", "avi", "video", "movie"}:
            return
        # DETECT SEASON
        season = detect_season(text)

        # DETECT YEAR
        year = detect_year(text)

        # DETECT COMBINED
        combined = detect_combined(text)

        # DETECT LANGUAGE
        languages = await detect_languages(text)

        # DETECT HALL PRINT
        hall_print = detect_hall_print(text)

        # CACHE KEY
        cache_key = build_cache_key(title, season, year)

        # CHECK CACHE
        if is_already_notified(cache_key):
            return

        # SAVE CACHE
        save_notification(cache_key)

        # BUILD CAPTION
        caption_text = await build_caption(
            title=title,
            season=season,
            year=year,
            languages=languages,
            combined=combined,
            hall_print=hall_print
        )

        # SEND MESSAGE
        safe_title = re.sub(r'[^a-zA-Z0-9 ]', '', title)
        safe_title = safe_title.replace(" ", "-")

        get_file = f"https://telegram.me/{temp.U_NAME}?start=getfile-{safe_title}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 Tap To Search", url=get_file)]
        ])

        await bot.send_message(
            chat_id=MOVIE_UPDATE_CHANNEL,
            text=caption_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    except Exception as e:
        LOGGER.error(f"Update Error: {e}")
    

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
    
async def send_with_visual(bot, caption: str, tmdb_data: Dict, search_movie):
    try:
        visual_url = await get_best_visual(tmdb_data)
        get_file = f'https://telegram.me/{temp.U_NAME}?start=getfile-{search_movie}'
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Get File", url=get_file)],
            get_trailer_button(tmdb_data)
        ])
        
        if visual_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(visual_url, timeout=aiohttp.ClientTimeout(total=20)) as img_resp:
                    if img_resp.status == 200:
                        img_bytes = await img_resp.read()
                        photo_file = io.BytesIO(img_bytes)
                        photo_file.name = await generate_premium_filename(tmdb_data["title"])
                        
                        await bot.send_photo(
                            chat_id=MOVIE_UPDATE_CHANNEL, 
                            photo=photo_file, 
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard
                        )
                        return       
        await bot.send_photo(
            chat_id=MOVIE_UPDATE_CHANNEL,
            photo=DEFAULT_IMAGE_URL,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )       
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
