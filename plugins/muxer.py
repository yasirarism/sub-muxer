from pyrogram import Client, filters
from helper_func.progress_bar import progress_bar
from helper_func.dbhelper import Database as Db
from helper_func.mux import softmux_vid, hardmux_vid, softremove_vid
from config import Config
from PIL import Image
import time
import logging
import os
import asyncio
from subprocess import check_output, run as srun
import json

db = Db()


async def _check_user(filt, c, m):
    chat_id = str(m.from_user.id)
    return chat_id in Config.ALLOWED_USERS


def get_media_info(path):

    try:
        result = check_output([
            "ffprobe", "-hide_banner", "-loglevel", "error", "-print_format",
            "json", "-show_format", path
        ]).decode('utf-8')
    except Exception as e:
        logging.error(f'{e} Mostly file not Found!')
        return 0, None, None

    fields = json.loads(result).get('format')
    if fields is None:
        logging.error(f"get_media_info: {result}")
        return 0, None, None

    duration = round(float(fields.get('duration', 0)))

    fields = fields.get('tags')
    if fields is not None:
        artist = fields.get('artist')
        if artist is None:
            artist = fields.get('ARTIST')
        title = fields.get('title')
        if title is None:
            title = fields.get('TITLE')
    else:
        title = None
        artist = None

    return duration, artist, title


def take_ss(video_file):
    des_dir = 'Thumbnails'
    if not os.path.exists(des_dir):
        os.mkdir(des_dir)
    des_dir = os.path.join(des_dir, f"{time.time()}.jpg")
    duration = get_media_info(video_file)[0]
    if duration == 0:
        duration = 3
    duration = duration // 2

    status = srun([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss",
        str(duration), "-i", video_file, "-frames:v", "1", des_dir
    ])

    if status.returncode != 0 or not os.path.lexists(des_dir):
        return None

    with Image.open(des_dir) as img:
        img.convert("RGB").save(des_dir, "JPEG")

    return des_dir


check_user = filters.create(_check_user)


@Client.on_message(filters.command('softmux') & check_user & filters.private)
async def softmux(client, message):

    chat_id = message.from_user.id
    og_vid_filename = db.get_vid_filename(chat_id)
    og_sub_filename = db.get_sub_filename(chat_id)
    text = ''
    if not og_vid_filename:
        text += 'First send a Video File\n'
    if not og_sub_filename:
        text += 'Send a Subtitle File!'

    if not (og_sub_filename and og_vid_filename):
        await client.send_message(chat_id, text)
        return

    text = 'Your File is Being Soft Subbed. This should be done in few seconds!'
    sent_msg = await client.send_message(chat_id, text)

    softmux_filename = await softmux_vid(og_vid_filename, og_sub_filename,
                                         sent_msg)
    if not softmux_filename:
        return

    final_filename = db.get_filename(chat_id)
    os.rename(
        f'{Config.DOWNLOAD_DIR}/{softmux_filename}',
        f'{Config.DOWNLOAD_DIR}/{final_filename}',
    )

    start_time = time.time()
    try:
        await client.send_document(
            chat_id,
            progress=progress_bar,
            progress_args=('Uploading your File!', sent_msg, start_time),
            document=os.path.join(Config.DOWNLOAD_DIR, final_filename),
            caption=final_filename)
        text = f'File Successfully Uploaded!\nTotal Time taken : {round(time.time() - start_time)} seconds'
        await sent_msg.edit(text)
    except Exception as e:
        print(e)
        await client.send_message(
            chat_id,
            'An error occured while uploading the file!\nCheck logs for details of the error!'
        )

    path = f'{Config.DOWNLOAD_DIR}/'
    os.remove(path + og_sub_filename)
    os.remove(path + og_vid_filename)
    try:
        os.remove(path + final_filename)
    except:
        pass

    db.erase(chat_id)


@Client.on_message(filters.command('hardmux') & check_user & filters.private)
async def hardmux(client, message):

    chat_id = message.from_user.id
    og_vid_filename = db.get_vid_filename(chat_id)
    og_sub_filename = db.get_sub_filename(chat_id)
    text = ''
    if not og_vid_filename:
        text += 'First send a Video File\n'
    if not og_sub_filename:
        text += 'Send a Subtitle File!'

        if not og_vid_filename:
            return await client.send_message(chat_id, text)

    text = 'Your File is Being Hard Subbed. This might take a long time!'
    sent_msg = await client.send_message(chat_id, text)

    hardmux_filename = await hardmux_vid(og_vid_filename, og_sub_filename,
                                         sent_msg)

    if not hardmux_filename:
        return

    final_filename = db.get_filename(chat_id)
    os.rename(
        f'{Config.DOWNLOAD_DIR}/{hardmux_filename}',
        f'{Config.DOWNLOAD_DIR}/{final_filename}',
    )

    start_time = time.time()
    duration = get_media_info(os.path.join(Config.DOWNLOAD_DIR,
                                           final_filename))[0]
    thumb = take_ss(os.path.join(Config.DOWNLOAD_DIR, final_filename))
    if thumb is not None:
        with Image.open(thumb) as img:
            width, height = img.size
    else:
        width = 480
        height = 320
    try:
        await client.send_video(chat_id,
                                progress=progress_bar,
                                progress_args=('Uploading your File!',
                                               sent_msg, start_time),
                                video=os.path.join(Config.DOWNLOAD_DIR,
                                                   final_filename),
                                caption=final_filename,
                                duration=duration,
                                supports_streaming=True,
                                thumb=thumb,
                                width=width,
                                height=height)
        text = f'File Successfully Uploaded!\nTotal Time taken : {round(time.time() - start_time)} seconds'
        await sent_msg.edit(text)
    except Exception as e:
        print(e)
        await client.send_message(
            chat_id,
            'An error occured while uploading the file!\nCheck logs for details of the error!'
        )

    path = f'{Config.DOWNLOAD_DIR}/'
    os.remove(path + og_sub_filename)
    os.remove(path + og_vid_filename)
    try:
        os.remove(path + final_filename)
    except:
        pass
    db.erase(chat_id)


@Client.on_message(
    filters.command('softremove') & check_user & filters.private)
async def softremove(client, message):

    chat_id = message.from_user.id
    og_vid_filename = db.get_vid_filename(chat_id)
    og_sub_filename = db.get_sub_filename(chat_id)
    text = ''
    if not og_vid_filename:
        text += 'First send a Video File\n'
    if not og_sub_filename:
        text += 'Send a Subtitle File!'

    if not (og_sub_filename and og_vid_filename):
        await client.send_message(chat_id, text)
        return

    text = 'Your File is Being Soft Subbed. This should be done in few seconds!'
    sent_msg = await client.send_message(chat_id, text)

    softmux_filename = await softremove_vid(og_vid_filename, og_sub_filename,
                                            sent_msg)
    if not softmux_filename:
        return

    final_filename = db.get_filename(chat_id)
    os.rename(
        f'{Config.DOWNLOAD_DIR}/{softmux_filename}',
        f'{Config.DOWNLOAD_DIR}/{final_filename}',
    )

    start_time = time.time()
    try:
        await client.send_document(
            chat_id,
            progress=progress_bar,
            progress_args=('Uploading your File!', sent_msg, start_time),
            document=os.path.join(Config.DOWNLOAD_DIR, final_filename),
            caption=final_filename)
        text = f'File Successfully Uploaded!\nTotal Time taken : {round(time.time() - start_time)} seconds'
        await sent_msg.edit(text)
    except Exception as e:
        print(e)
        await client.send_message(
            chat_id,
            'An error occured while uploading the file!\nCheck logs for details of the error!'
        )

    path = f'{Config.DOWNLOAD_DIR}/'
    os.remove(path + og_sub_filename)
    os.remove(path + og_vid_filename)
    try:
        os.remove(path + final_filename)
    except:
        pass

    db.erase(chat_id)
