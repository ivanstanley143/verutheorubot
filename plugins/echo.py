

from urllib.parse import urlparse
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
import requests, urllib.parse, filetype, os, time, shutil, tldextract, asyncio, json, math
from PIL import Image
from plugins.config import Config
from plugins.script import Translation
logging.getLogger("pyrogram").setLevel(logging.WARNING)
from pyrogram import filters
import os
import time
import random
from pyrogram import enums
from pyrogram import Client
from plugins.functions.verify import verify_user, check_token, check_verification, get_token
from plugins.functions.forcesub import handle_force_subscribe
from plugins.functions.display_progress import humanbytes
from plugins.functions.help_uploadbot import DownLoadFile
from plugins.functions.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from plugins.functions.ran_text import random_char
from plugins.database.database import db
from plugins.database.add import AddUser
from pyrogram.types import Thumbnail



@Client.on_message(filters.private & filters.regex(pattern=".*http.*"))
async def echo(bot, update): 

    if Config.LOG_CHANNEL:
        try:
            log_message = await update.forward(Config.LOG_CHANNEL)
            log_info = "Message Sender Information\n"
            log_info += "\nFirst Name: " + update.from_user.first_name
            log_info += "\nUser ID: " + str(update.from_user.id)
            log_info += "\nUsername: @" + (update.from_user.username if update.from_user.username else "")
            log_info += "\nUser Link: " + update.from_user.mention
            await log_message.reply_text(
                text=log_info,
                disable_web_page_preview=True,
                quote=True
            )
        except Exception as error:
            print(error)

    if not update.from_user:
        return await update.reply_text("I don't know about you sar :(")

    await AddUser(bot, update)

    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, update)
        if fsub == 400:
            return

    logger.info(update.from_user)
    url = update.text

    # ---------- DIRECT FILE CHECK (FIXED INDENTATION) ----------
    parsed = urlparse(url)
    path = parsed.path.lower()

    DIRECT_EXTENSIONS = (
        ".mkv", ".mp4", ".avi", ".mov", ".webm",
        ".mp3", ".flac", ".wav",
        ".zip", ".rar", ".7z",
        ".srt", ".ass"
    )

    if path.endswith(DIRECT_EXTENSIONS):
        cb_string_video = "video=direct=none"
        cb_string_file = "file=direct=none"

        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("🎥 Video", callback_data=cb_string_video),
                InlineKeyboardButton("📁 Document", callback_data=cb_string_file)
            ]]
        )

        await update.reply_text(
            Translation.FORMAT_SELECTION,
            reply_markup=keyboard,
            disable_web_page_preview=True,
            quote=True
        )
        return
    # ---------- END DIRECT FILE CHECK ----------

    youtube_dl_username = None
    youtube_dl_password = None
    file_name = None

    print(url)

    if "|" in url:
        url_parts = url.split("|")
        if len(url_parts) == 2:
            url = url_parts[0]
            file_name = url_parts[1]
        elif len(url_parts) == 4:
            url = url_parts[0]
            file_name = url_parts[1]
            youtube_dl_username = url_parts[2]
            youtube_dl_password = url_parts[3]
        else:
            for entity in update.entities:
                if entity.type == "text_link":
                    url = entity.url
                elif entity.type == "url":
                    o = entity.offset
                    l = entity.length
                    url = url[o:o + l]

        if url is not None:
            url = url.strip()
        if file_name is not None:
            file_name = file_name.strip()
        if youtube_dl_username is not None:
            youtube_dl_username = youtube_dl_username.strip()
        if youtube_dl_password is not None:
            youtube_dl_password = youtube_dl_password.strip()

        logger.info(url)
        logger.info(file_name)

    else:
        for entity in update.entities:
            if entity.type == "text_link":
                url = entity.url
            elif entity.type == "url":
                o = entity.offset
                l = entity.length
                url = url[o:o + l]

    if Config.HTTP_PROXY != "":
        command_to_exec = [
            "yt-dlp",
            "--no-warnings",
            "--allow-dynamic-mpd",
            "--no-check-certificate",
            url,
            "--proxy", Config.HTTP_PROXY
        ]
    else:
        command_to_exec = [
            "yt-dlp",
            "--no-warnings",
            "--allow-dynamic-mpd",
            "--no-check-certificate",
            url,
            "--geo-bypass-country",
            "IN"
        ]

    if youtube_dl_username is not None:
        command_to_exec.extend(["--username", youtube_dl_username])
    if youtube_dl_password is not None:
        command_to_exec.extend(["--password", youtube_dl_password])

    logger.info(command_to_exec)

    chk = await bot.send_message(
        chat_id=update.chat.id,
        text="Pʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ ⌛",
        disable_web_page_preview=True,
        reply_to_message_id=update.id,
        parse_mode=enums.ParseMode.HTML
    )

    process = await asyncio.create_subprocess_exec(
        *command_to_exec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()

    if e_response and "nonnumeric port" not in e_response:
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.NO_VOID_FORMAT_FOUND.format(e_response),
            reply_to_message_id=update.id
        )
        return

    inline_keyboard = [[
        InlineKeyboardButton("📁 ᴍᴇᴅɪᴀ", callback_data="video=OFL=ENON")
    ]]

    await chk.delete()
    await bot.send_message(
        chat_id=update.chat.id,
        text=Translation.FORMAT_SELECTION,
        reply_markup=InlineKeyboardMarkup(inline_keyboard),
        reply_to_message_id=update.id
    )
