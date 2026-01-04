import time
import urllib.parse
from plugins.functions.display_progress import humanbytes

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import os
import requests

def DetectFileSize(url):
    r = requests.get(url, allow_redirects=True, stream=True)
    total_size = int(r.headers.get("content-length", 0))
    return total_size

def get_filename_from_url(url):
    parsed = urllib.parse.urlparse(url)
    name = os.path.basename(parsed.path)
    name = urllib.parse.unquote(name)
    return name if name else "file.bin"
    
def DownLoadFile(url, file_name, chunk_size, client, ud_type, message_id, chat_id):

    # ✅ Auto-detect filename if not provided
    if not file_name:
        file_name = get_filename_from_url(url)

    # ✅ Remove old file if exists
    if os.path.exists(file_name):
        os.remove(file_name)

    if not url:
        return file_name

    r = requests.get(url, allow_redirects=True, stream=True)
    total_size = int(r.headers.get("content-length", 0))
    downloaded_size = 0

    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
                downloaded_size += len(chunk)   # ✅ FIXED

            # Progress update
            if client is not None and total_size > 0:
                if downloaded_size % (5 * 1024 * 1024) < chunk_size:
                    try:
                        client.edit_message_text(
                            chat_id,
                            message_id,
                            text="{}: {} of {}".format(
                                ud_type,
                                humanbytes(downloaded_size),
                                humanbytes(total_size)
                            )
                        )
                    except:
                        pass

    return file_name
