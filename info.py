import re
import os
from os import environ, getenv
from Script import script

id_pattern = re.compile(r'^.\d+$')
LANDSCAPE_POSTER = environ.get("LANDSCAPE_POSTER", "True").lower() == "true"

def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

def parse_channel_list(env_value):
    if not env_value:
        return []
    channels = []
    for ch in env_value.split():
        ch = ch.strip()
        if id_pattern.search(ch):
            channels.append(int(ch))
    return channels

# 🔒 Permanent Direct Join Channels
GLOBAL_FSUB_CHANNELS = parse_channel_list(
    os.environ.get("GLOBAL_FSUB_CHANNELS", "")
)

# 🔒 Permanent Request Join Channels
GLOBAL_REQ_FSUB_CHANNELS = parse_channel_list(
    os.environ.get("GLOBAL_REQ_FSUB_CHANNELS", "")
)

SESSION = environ.get('SESSION', 'media_search')
API_ID = int(environ.get('API_ID', ''))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', "")

CACHE_TIME = int(environ.get('CACHE_TIME', 300))
USE_CAPTION_FILTER = bool(environ.get('USE_CAPTION_FILTER', True))

PICS = (environ.get('PICS', 'https://i.ibb.co/G62BfhM/photo-2025-12-12-02-06-06-7582787047673298968.jpg https://i.ibb.co/DHjPQKDT/photo-2025-12-22-05-05-09-7586552209278500880.jpg https://i.ibb.co/ymWWLd2D/photo-2025-12-22-05-05-09-7586543967236259856.jpg https://i.ibb.co/VYmt4TDS/photo-2025-12-22-05-04-30-7586543829797306372.jpg https://i.ibb.co/9mHqK8Sn/photo-2025-12-22-05-05-00-7586552114789220396.jpg https://i.ibb.co/HfRbmQZy/photo-2025-12-22-05-05-08-7586552076134514732.jpg https://i.ibb.co/TMMZdB5S/photo-2025-12-22-05-05-00-7586552050364710916.jpg https://i.ibb.co/MD6wT06K/photo-2025-12-22-05-05-09-7586552011710005264.jpg https://i.ibb.co/MyyTgQMn/photo-2025-12-22-05-04-59-7586551981645234216.jpg https://i.ibb.co/jkNrTM7h/photo-2025-12-22-05-05-07-7586551947285495828.jpg https://i.ibb.co/wNm9v1fM/photo-2025-12-22-05-05-07-7586544010185932804.jpg https://i.ibb.co/ymWWLd2D/photo-2025-12-22-05-05-09-7586543967236259856.jpg')).split() 
NOR_IMG = environ.get("NOR_IMG", "https://graph.org/file/62efbcc4e7580b76530ba.jpg")
MELCOW_VID = environ.get("MELCOW_VID", "https://graph.org/file/e215d12bfd4fa2155e90e.mp4")
SPELL_IMG = environ.get("SPELL_IMG", "https://graph.org/file/13702ae26fb05df52667c.jpg")
SUBSCRIPTION = (environ.get('SUBSCRIPTION', 'https://i.ibb.co/69DZpdH/photo-2025-12-22-05-03-15-7586543743897960488.jpg'))
FSUB_IMG = (environ.get('FSUB_IMG', 'https://i.ibb.co/cShkPjcZ/x.jpg')).split() 

ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '7859995064').split()] 
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', '-1002533229703 -1002633335930 -1002533695302 -1003239941447').split()]
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '-1002900228022'))  
BIN_CHANNEL = int(environ.get('BIN_CHANNEL', '-1002900228022'))  
MOVIE_UPDATE_CHANNEL = int(environ.get('MOVIE_UPDATE_CHANNEL', '-1002900228022'))  
PREMIUM_LOGS = int(environ.get('PREMIUM_LOGS', '-1002900228022')) 
auth_grp = environ.get('AUTH_GROUP', '-1003464461159')
AUTH_GROUPS = [int(ch) for ch in auth_grp.split()] if auth_grp else None
reqst_channel = environ.get('REQST_CHANNEL_ID', '-1003444288916') 
REQST_CHANNEL = int(reqst_channel) if reqst_channel and id_pattern.search(reqst_channel) else None
support_chat_id = environ.get('SUPPORT_CHAT_ID', '-1003384592518') 
SUPPORT_CHAT_ID = int(support_chat_id) if support_chat_id and id_pattern.search(support_chat_id) else None

DATABASE_URI = environ.get('DATABASE_URI', "")
DATABASE_NAME = environ.get('DATABASE_NAME', "Cluster0")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'SilentXBotz_files')

# If MULTIPLE_DB Is True Then Fill DATABASE_URI2 Value Else You Will Get Error.
MULTIPLE_DB = is_enabled(os.environ.get('MULTIPLE_DB', "False"), False) # Type True For Turn On MULTIPLE DB FUNTION 
DATABASE_URI2 = environ.get('DATABASE_URI2', "")
DB_CHANGE_LIMIT = int(environ.get('DB_CHANGE_LIMIT', "432")) 

GRP_LNK = environ.get('GRP_LNK', 'https://t.me/Graduate_Request_Pro')
CHNL_LNK = environ.get('CHNL_LNK', 'https://t.me/Graduate_Movies')
OWNER_LNK = environ.get('OWNER_LNK', 'https://t.me/yours_swap_bot')
UPDATE_CHANNEL_LNK = environ.get('UPDATE_CHANNEL_LNK', 'https://t.me/Graduate_Movies')
SUPPORT_GRP = environ.get('SUPPORT_GRP', 'https://t.me/Gm_Support_chat')

AUTH_CHANNEL = environ.get("AUTH_CHANNEL", "") # add multiple channels here, separated by single space
#AUTH_REQ_CHANNEL = environ.get('AUTH_REQ_CHANNEL', '-1002738200399') # add multiple channels here, separated by single space

IS_VERIFY = is_enabled('IS_VERIFY', False)
LOG_VR_CHANNEL = int(environ.get('LOG_VR_CHANNEL', '-1002900228022'))
LOG_API_CHANNEL = int(environ.get('LOG_API_CHANNEL', '-1002900228022'))
VERIFY_IMG = environ.get("VERIFY_IMG", "https://telegra.ph/file/9ecc5d6e4df5b83424896.jpg")

TUTORIAL = environ.get("TUTORIAL", "https://t.me/graduate_movies")
TUTORIAL_2 = environ.get("TUTORIAL_2", "https://t.me/graduate_movies")
TUTORIAL_3 = environ.get("TUTORIAL_3", "https://t.me/graduate_movies")

SHORTENER_API = environ.get("SHORTENER_API", "01ea63cd92c767060e19f438be5e17248d1e68f5")
SHORTENER_WEBSITE = environ.get("SHORTENER_WEBSITE", "https://vplink.in")

SHORTENER_API2 = environ.get("SHORTENER_API2", "01ea63cd92c767060e19f438be5e17248d1e68f5")
SHORTENER_WEBSITE2 = environ.get("SHORTENER_WEBSITE2", "https://vplink.in")

SHORTENER_API3 = environ.get("SHORTENER_API3", "01ea63cd92c767060e19f438be5e17248d1e68f5")
SHORTENER_WEBSITE3 = environ.get("SHORTENER_WEBSITE3", "https://vplink.in")

TWO_VERIFY_GAP = int(environ.get('TWO_VERIFY_GAP', "1200"))
THREE_VERIFY_GAP = int(environ.get('THREE_VERIFY_GAP', "54000"))

#Smart Select Mode
SMART_SELECTION_MODE = environ.get("SMART_SELECTION_MODE", "false").lower() == "true"
#_________________Swapno Adaption_______________

MOVIE_UPDATE_NOTIFICATION = bool(environ.get("MOVIE_UPDATE_NOTIFICATION", True))
NO_RESULTS_MSG = bool(environ.get("NO_RESULTS_MSG", True))
MAX_B_TN = environ.get("MAX_B_TN", "8")
MAX_BTN = is_enabled((environ.get('MAX_BTN', "True")), True)
PORT = environ.get("PORT", "8080")
#PORT = int(os.environ["PORT"])
MSG_ALRT = environ.get('MSG_ALRT', 'Share & Support Us ♥️')
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'https://t.me/Gm_Support_chat') 
P_TTI_SHOW_OFF = is_enabled((environ.get('P_TTI_SHOW_OFF', "False")), False)
IMDB = is_enabled((environ.get('IMDB', "True")), False)
AUTO_FFILTER = is_enabled((environ.get('AUTO_FFILTER', "True")), True)
AUTO_DELETE = is_enabled((environ.get('AUTO_DELETE', "True")), True)
AUTO_DELETE_TIME = int(environ.get("AUTO_DELETE_TIME", "300"))  
LINK_MODE = is_enabled((environ.get('LINK_MODE', "True")), True)
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", f"{script.IMDB_TEMPLATE_TXT}")
LONG_IMDB_DESCRIPTION = is_enabled(environ.get("LONG_IMDB_DESCRIPTION", "False"), False)
SPELL_CHECK_REPLY = is_enabled(environ.get("SPELL_CHECK_REPLY", "True"), True)
MAX_LIST_ELM = int(environ.get("MAX_LIST_ELM") or 10) or None # Maximum number of elements in a list (default: 10, set 0 for no limit)
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))
FILE_STORE_CHANNEL = [int(ch) for ch in (environ.get('FILE_STORE_CHANNEL', '-1002533229703')).split()]
MELCOW_NEW_USERS = is_enabled((environ.get('MELCOW_NEW_USERS', "False")), False)
PROTECT_CONTENT = is_enabled((environ.get('PROTECT_CONTENT', "False")), True)
PM_SEARCH = bool(environ.get('PM_SEARCH', True)) 
EMOJI_MODE = bool(environ.get('EMOJI_MODE', True)) 
PAID_STREAM = bool(environ.get('PAID_STREAM', False)) 
STREAM_MODE = bool(environ.get('STREAM_MODE', False))
MAINTENANCE_MODE = bool(environ.get('MAINTENANCE_MODE', False)) 

# ===== DAILY FILE LIMIT =====
DAILY_LIMIT_ENABLED = os.getenv("DAILY_LIMIT_ENABLED", "true").lower() == "true" # daily file limit on/off
DAILY_TOTAL_LIMIT = int(os.getenv("DAILY_TOTAL_LIMIT", "5")) # total dailty file 
DAILY_LIMIT = DAILY_LIMIT_ENABLED
LIMIT_LESS_USERS = [
    int(x) for x in os.getenv("LIMIT_LESS_USERS", "7859995064").strip().split()
]
IGNORE_WORDS = (list(os.environ.get("IGNORE_WORDS").split(",")) if os.environ.get("IGNORE_WORDS") else []) #Remove Words While Searching Files
IGNORE_WORDS = [
    "movies", "movie", "episode", "episodes", "south indian", "south indian movie",
    "south movie", "south indian", "web-series", "web series", "webseries", "hindi me bhejo",
    "ful", "!", "kro", "jaldi", "audio", "language", "mkv", "mp4", "web", "series",
    "hollywood", "all", "bollywood", "south", "hd", "karo", "upload", "bhejo",
    "fullepisode", "bengali", "please", "plz", "hindi", "seasons", "request", "#request", "send", "link", "dabbbed", "dubbed",
]
#Image Host 
IMGBB_API_KEY = os.environ["IMGBB_API_KEY"]

BAD_WORDS = ["Hdhub4u", "cinevood", "skymoviedHD", "hdmovie2.productions", "hdmovie2", "4khdhub", "Toonworld4all", "TW4ALL", "ExtraFlix", "Hdhub", "Movies", "Movies4u", "movies4u", "Vegamovies", "extraflix", "hdholly", "Filmy4wap", "Filmu4cab", "Tamilmv", "CineVood", "Hub4u", "Hub4", "SkymoviesHD", "Skymovieshd", "telegram", "tg", "TG", "Telegram", "HdWebMovies", "mkvcinemas", "mkvCinemas", "mkvking", "5moviez", "hdm2", "mkvcinema", "1tamil", "1tamilmv", "1Tamil", "1tamilblaster", "1TamilBlaster", "Moviez", "moviez", "yts mx", "YTS", "YTS MX", "mkvCinem", "filmyzilla", "filmzilla", "CineVood", "BT MOVIES HD", "FILMSCLUB04", "XDMovies", "mp4movies", "mp4moviez", "MLWBD", "MLSBD", "mlsbd", "mlwbd", "FibWatch", "fibwatch", "Joya9tv", "joya9tv", "Cinedoze", "CineDoze", "cinedoze", "world4u", "SSRMovies", "SSRmovies", "5MovieRulz", "FilmyCab"] #remove words form file name 
LANGUAGES = ["malayalam", "", "tamil", "", "english", "", "hindi", "", "telugu", "", "kannada", "", "gujarati", "", "marathi", "", "punjabi", "", "bengali", ""]
QUALITIES = ["360P", "", "480P", "", "720P", "", "1080P", "", "1440P", "", "2160P", "", "4k", ""]
SEASONS = ["s01" , "s02" , "s03" , "s04", "s05" , "s06" , "s07" , "s08" , "s09" , "s10" , "s11" , "s12"]

#Smart Mode Buttons
SMART_LANG_MAP = {
    "malayalam": {
        "label": "ᴍᴀʟᴀʏᴀʟᴀᴍ",
        "aliases": ["malayalam", "mal"]
    },
    "tamil": {
        "label": "ᴛᴀᴍɪʟ",
        "aliases": ["tamil", "tam"]
    },
    "english": {
        "label": "ᴇɴɢʟɪꜱʜ",
        "aliases": ["english", "eng"]
    },
    "hindi": {
        "label": "ʜɪɴᴅɪ",
        "aliases": ["hindi", "hin"]
    },
    "telugu": {
        "label": "ᴛᴇʟᴜɢᴜ",
        "aliases": ["telugu", "tel"]
    },
    "kannada": {
        "label": "ᴋᴀɴɴᴀᴅᴀ",
        "aliases": ["kannada", "kan"]
    },
    "gujarati": {
        "label": "ɢᴜᴊᴀʀᴀᴛɪ",
        "aliases": ["gujarati", "guj"]
    },
    "marathi": {
        "label": "ᴍᴀʀᴀᴛʜɪ",
        "aliases": ["marathi", "mar"]
    },
    "punjabi": {
        "label": "ᴘᴜɴᴊᴀʙɪ",
        "aliases": ["punjabi", "pan"]
    },
    "bengali": {
        "label": "ʙᴇɴɢᴀʟɪ",
        "aliases": ["bengali", "bangla", "ben"]
    },

    # 🌏 Extra Asian Languages
    "japanese": {
        "label": "ᴊᴀᴘᴀɴᴇꜱᴇ",
        "aliases": ["japanese", "jpn", "jap"]
    },
    "korean": {
        "label": "ᴋᴏʀᴇᴀɴ",
        "aliases": ["korean", "kor"]
    },
    "chinese": {
        "label": "ᴄʜɪɴᴇꜱᴇ",
        "aliases": ["chinese", "chi", "chn"]
    }
}

SMART_QUALITY_REGEX = r"(2160p|1440p|1080p|720p|480p|360p|4k)"

SMART_SEASON_REGEX = [
    r"\bs\d{1,2}e\d{1,2}\b",
    r"\bs\d{1,2}\b",
    r"\bseason\s*\d{1,2}\b"
]

NO_PORT = bool(environ.get('NO_PORT', False))
APP_NAME = None
if 'DYNO' in environ:
    ON_HEROKU = True
    APP_NAME = environ.get('APP_NAME')
else:
    ON_HEROKU = False
BIND_ADRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
FQDN = str(getenv('FQDN', BIND_ADRESS)) if not ON_HEROKU or getenv('FQDN') else APP_NAME+'.herokuapp.com'
URL = "https://{}/".format(FQDN) if ON_HEROKU or NO_PORT else "https://{}/".format(FQDN, PORT)
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
WORKERS = int(environ.get('WORKERS', '4'))
SESSION_NAME = str(environ.get('SESSION_NAME', 'GraduatexBotz'))
MULTI_CLIENT = False
name = str(environ.get('name', 'SilentX'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
if 'DYNO' in environ:
    ON_HEROKU = True
    APP_NAME = str(getenv('APP_NAME'))
else:
    ON_HEROKU = False
HAS_SSL = bool(getenv('HAS_SSL', False))
if HAS_SSL:
    URL = "https://{}/".format(FQDN)
else:
    URL = "http://{}/".format(FQDN)


REACTIONS = ["🤝", "😇", "🤗", "😍", "👍", "🎅", "😐", "🥰", "🤩", "😱", "🤣", "😘", "👏", "😛", "😈", "🎉", "⚡️", "🫡", "🤓", "😎", "🏆", "🔥", "🤭", "🌚", "🆒", "👻", "😁"]

STAR_PREMIUM_PLANS = {
    1: "7day",
    30: "15day",    
    60: "1month", 
    120: "2month",   
}

Bot_cmds = {
    "start": "ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ",
    #"trendlist": "ɢᴇᴛ ᴛᴏᴘ ꜱᴇᴀʀᴄʜ ʟɪꜱᴛ",
    #"myplan" : "ᴄʜᴇᴄᴋ ᴘʀᴇᴍɪᴜᴍ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ",
    #"plan" :"ᴄʜᴇᴄᴋ ᴘʀᴇᴍɪᴜᴍ ᴘʀɪᴄᴇ",
    "settings": "ᴄʜᴀɴɢᴇ sᴇᴛᴛɪɴɢs",
    #"group_cmd": "ᴅᴇʟᴇᴛᴇ ᴀ ꜱᴘᴇᴄɪꜰɪᴄ ꜰɪʟᴇ ꜰʀᴏᴍ ᴅʙ.",
    #"admin_cmd": "ᴅᴇʟᴇᴛᴇ ᴀ ꜱᴘᴇᴄɪꜰɪᴄ ꜰɪʟᴇ ꜰʀᴏᴍ ᴅʙ.",
    #"details": "ꜱᴇᴇ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ",
    "maintenance": "on/off",
    "reset_group": "ʀᴇꜱᴇᴛ ɢʀᴏᴜᴘ ꜱᴇᴛᴛɪɴɢꜱ", 
    "stats": "ᴄʜᴇᴄᴋ ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ.",
    #"delete": "ᴅᴇʟᴇᴛᴇ ᴀ ꜱᴘᴇᴄɪꜰɪᴄ ꜰɪʟᴇ ꜰʀᴏᴍ ᴅʙ.",
    #"movie_update": "ᴏɴ ᴏғғ ᴀᴄᴄᴏʀᴅɪɴɢ ʏᴏᴜʀ ɴᴇᴇᴅᴇᴅ...",
    "pm_search": "ᴘᴍ sᴇᴀʀᴄʜ ᴏɴ ᴏғғ ᴀᴄᴄᴏʀᴅɪɴɢ ʏᴏᴜʀ ɴᴇᴇᴅᴇᴅ...",
    "restart": "ʀᴇꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ.",
    "broadcast": "ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴀssᴀɢᴇ."
}

#Don't Change Anything Here

if MULTIPLE_DB == False:
    DATABASE_URI = DATABASE_URI
    DATABASE_URI2 = DATABASE_URI
else:
    DATABASE_URI = DATABASE_URI
    DATABASE_URI2 = DATABASE_URI2

AUTH_CHANNEL = [int(ch) for ch in AUTH_CHANNEL.strip().split()] if AUTH_CHANNEL else []
#AUTH_REQ_CHANNEL = [int(ch) for ch in AUTH_REQ_CHANNEL.strip().split()] if AUTH_REQ_CHANNEL else []

class temp:
    U_NAME = "file_099_bot"
