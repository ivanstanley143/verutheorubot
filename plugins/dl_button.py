from urllib.parse import urlparse, unquote

def clean_name(name: str) -> str:
    """
    Cleans filename for quality and language detection
    """
    name = unquote(name)          # %2B → +
    name = name.replace("+", " ") # + → space
    name = name.lower()           # make lowercase
    return name

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import asyncio
import aiohttp
import os
import time
from datetime import datetime

from plugins.config import Config
from plugins.script import Translation
from plugins.thumbnail import *
from plugins.database.database import db
from plugins.functions.display_progress import (
    progress_for_pyrogram,
    humanbytes,
    TimeFormatter
)

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram import enums


# ---------------- VIDEO INFO ---------------- #

def get_video_info(file_path, file_name=""):
    quality = "Unknown"
    duration = "Unknown"

    # 1️⃣ Try reading video metadata
    try:
        parser = createParser(file_path)
        if parser:
            metadata = extractMetadata(parser)
            if metadata:
                if metadata.has("height"):
                    quality = f"{metadata.get('height')}p"

                if metadata.has("duration"):
                    seconds = metadata.get("duration").seconds
                    h = seconds // 3600
                    m = (seconds % 3600) // 60
                    s = seconds % 60
                    duration = f"{h}h {m}m {s}s"
    except:
        pass

    # 2️⃣ If quality not found → detect from filename
    if quality == "Unknown" and file_name:
        name = clean_name(file_name)

        if "2160p" in name or "4k" in name:
            quality = "2160p"
        elif "1080p" in name:
            quality = "1080p"
        elif "720p" in name:
            quality = "720p"
        elif "480p" in name:
            quality = "480p"

    return quality, duration


# ---------------- CALLBACK ---------------- #

async def ddl_call_back(bot, update):
    logger.info(update)

    tg_send_type, youtube_dl_format, youtube_dl_ext = update.data.split("=")

    youtube_dl_url = update.message.reply_to_message.text
    parsed_url = urlparse(youtube_dl_url)

    custom_file_name = unquote(os.path.basename(parsed_url.path)).replace("+", " ")

    if "|" in youtube_dl_url:
        url_parts = youtube_dl_url.split("|")
        if len(url_parts) == 2:
            youtube_dl_url, custom_file_name = url_parts

    start = datetime.now()

    await update.message.edit_caption(
        caption=Translation.DOWNLOAD_START,
        parse_mode=enums.ParseMode.HTML
    )

    user_dir = f"{Config.DOWNLOAD_LOCATION}/{update.from_user.id}"
    os.makedirs(user_dir, exist_ok=True)

    download_path = f"{user_dir}/{custom_file_name}"
    final_name = os.path.basename(download_path)

    async with aiohttp.ClientSession() as session:
        try:
            await download_coroutine(
                bot,
                session,
                youtube_dl_url,
                download_path,
                update.message.chat.id,
                update.message.id,
                time.time()
            )
        except asyncio.TimeoutError:
            await bot.edit_message_text(
                Translation.SLOW_URL_DECED,
                update.message.chat.id,
                update.message.id
            )
            return

    if not os.path.exists(download_path):
        await update.message.edit_caption(
            Translation.NO_VOID_FORMAT_FOUND.format("Incorrect Link"),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # -------- METADATA -------- #

    quality, duration = get_video_info(download_path, custom_file_name)

    file_lower = custom_file_name.lower()
    languages = []

    if "malayalam" in file_lower or "mal" in file_lower:
        languages.append("Malayalam")
    if "tamil" in file_lower or "tam" in file_lower:
        languages.append("Tamil")
    if "telugu" in file_lower or "tel" in file_lower:
        languages.append("Telugu")
    if "hindi" in file_lower or "hin" in file_lower:
        languages.append("Hindi")
    if "english" in file_lower or "eng" in file_lower:
        languages.append("English")

    language = " + ".join(languages)   # no "Unknown"

    title = os.path.splitext(custom_file_name)[0]
    title = unquote(title)
    title = title.replace("+", " ").replace("_", " ").replace(".", " ")
    title = " ".join(title.split())

    description = f"<b>{title}</b>\n\n"
    description += f"🎬 <b>{quality}</b>\n"
    description += f"⏱ <b>{duration}</b>\n"

    if language:
        description += f"🔊 <b>{language}</b>"

    await update.message.edit_caption(
        caption=Translation.UPLOAD_START,
        parse_mode=enums.ParseMode.HTML
    )

    file_size = os.stat(download_path).st_size
    if file_size > Config.TG_MAX_FILE_SIZE:
        await update.message.edit_caption(
            Translation.RCHD_TG_API_LIMIT,
            parse_mode=enums.ParseMode.HTML
        )
        return

    start_time = time.time()

    # -------- UPLOAD -------- #

    if not await db.get_upload_as_doc(update.from_user.id):
        thumb = await Gthumb01(bot, update)
        await update.message.reply_document(
            document=download_path,
            file_name=final_name,
            caption=description,
            thumb=thumb,
            parse_mode=enums.ParseMode.HTML,
            progress=progress_for_pyrogram,
            progress_args=(Translation.UPLOAD_START, update.message, start_time)
        )
    else:
        width, height, dur = await Mdata01(download_path)
        thumb = await Gthumb02(bot, update, dur, download_path)
        await update.message.reply_video(
            video=download_path,
            file_name=final_name,
            caption=description,
            duration=dur,
            width=width,
            height=height,
            supports_streaming=True,
            thumb=thumb,
            parse_mode=enums.ParseMode.HTML,
            progress=progress_for_pyrogram,
            progress_args=(Translation.UPLOAD_START, update.message, start_time)
        )

    # -------- CLEANUP -------- #

    try:
        os.remove(download_path)
    except:
        pass

    end = datetime.now()
    await update.message.edit_caption(
        Translation.AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(
            (end - start).seconds,
            int(time.time() - start_time)
        ),
        parse_mode=enums.ParseMode.HTML
    )


# ---------------- DOWNLOAD (FIXED) ---------------- #

async def download_coroutine(bot, session, url, file_name, chat_id, message_id, start):
    downloaded = 0
    last_update_time = start
    last_downloaded = 0

    async with session.get(url, timeout=Config.PROCESS_MAX_TIMEOUT) as response:
        total_length = int(response.headers.get("Content-Length", 0))

        await bot.edit_message_text(
            chat_id,
            message_id,
            f"Initiating Download\n"
            f"File Size: {humanbytes(total_length)}",
            parse_mode=None   # ✅ IMPORTANT
        )

        with open(file_name, "wb") as f:
            while True:
                chunk = await response.content.read(Config.CHUNK_SIZE)
                if not chunk:
                    break

                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()

                # Update every 2 seconds (FAST + SAFE)
                if now - last_update_time >= 2:
                    speed = (downloaded - last_downloaded) / (now - last_update_time)
                    eta = (total_length - downloaded) / speed if speed > 0 else 0

                    progress_text = (
                        f"Downloading...\n\n"
                        f"Downloaded: {humanbytes(downloaded)} / {humanbytes(total_length)}\n"
                        f"Speed: {humanbytes(speed)}/s\n"
                        f"ETA: {TimeFormatter(int(eta * 1000))}"
                    )

                    try:
                        await bot.edit_message_text(
                            chat_id,
                            message_id,
                            progress_text,
                            parse_mode=None   # ✅ NEVER HTML HERE
                        )
                    except:
                        pass

                    last_update_time = now
                    last_downloaded = downloaded
