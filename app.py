import asyncio
import base64
import datetime
import logging
import re
import shutil
from typing import Any

import python_socks

from telethon import TelegramClient, events, Button
import coloredlogs
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault, Message

from async_aria2_client import AsyncAria2Client
from configer import API_ID, API_HASH, PROXY_IP, PROXY_PORT, BOT_TOKEN, ADMIN_ID, RPC_SECRET, RPC_URL
from util import get_file_name, progress, byte2_readable, hum_convert

coloredlogs.install(level='INFO')
log = logging.getLogger('bot')

proxy = (python_socks.ProxyType.HTTP, PROXY_IP, PROXY_PORT) if PROXY_IP is not None else None
bot = TelegramClient('./db/bot', API_ID, API_HASH, proxy=proxy).start(bot_token=BOT_TOKEN)
client = AsyncAria2Client(RPC_SECRET, f'ws://{RPC_URL}', bot)


@bot.on(events.NewMessage(pattern="/start"))
async def handler(event):
    await event.reply(f"aria2控制机器人,点击复制你的 ADMIN_ID:<code>{event.chat_id}</code>", parse_mode='html',
                      buttons=get_menu())


@bot.on(events.NewMessage(pattern="/web", from_users=ADMIN_ID))
async def handler(event):
    base_key = base64.b64encode(RPC_SECRET.encode("utf-8")).decode('utf-8')
    await event.respond(f'http://ariang.js.org/#!/settings/rpc/set/ws/{RPC_URL.replace(":", "/", 1)}/{base_key}')


@bot.on(events.NewMessage(pattern="/info", from_users=ADMIN_ID))
async def handler(event):
    pass


@bot.on(events.NewMessage(pattern="/path", from_users=ADMIN_ID))
async def handler(event):
    text = event.raw_text
    text = text.replace('/path ', '').strip()
    params = [{"dir": text}]
    data = await client.change_global_option(params)
    if data['result'] == 'OK':
        await event.respond(f'默认路径设置成功 {text}\n'
                            f'注意: docker启动的话，要在配置文件docker-compose.yml中配置挂载目录')
    else:
        await event.respond(f'默认路径设置失败 {text}')


@bot.on(events.NewMessage(pattern="/help"))
async def handler(event):
    await event.reply(f'''
开启菜单: <code>/start</code>
关闭菜单: <code>/close</code>
系统信息: <code>/info</code>
更换默认下载目录: <code>/path 绝对路径（如 /root/）</code>
ADMIN_ID:<code>{event.chat_id}</code>
    ''', parse_mode='html', buttons=[
        Button.url('更多帮助', 'https://github.com/jw-star/aria2bot')
    ])


@bot.on(events.NewMessage(from_users=ADMIN_ID))
async def send_welcome(event):
    text = event.raw_text
    log.info(str(datetime.datetime.now()) + ':' + text)
    if text == '⬇️正在下载':
        await downloading(event)
        return
    elif text == '⌛️ 正在等待':
        await waiting(event)
        return
    elif text == '✅ 已完成/停止':
        await stoped(event)
        return
    elif text == '⏸️暂停任务':
        await stop_task(event)
        return
    elif text == '▶️恢复任务':
        await unpause_task(event)
        return
    elif text == '❌ 删除任务':
        await remove_task(event)
        return
    elif text == '❌ ❌ 清空已完成/停止':
        await remove_all(event)
        return
    elif text == '关闭键盘':
        await event.reply("键盘已关闭,/menu 开启键盘", buttons=Button.clear())
        return
    # 获取输入信息
    if text.startswith('http'):
        url_arr = text.split('\n')
        for url in url_arr:
            await client.add_uri(
                uris=[url],
            )
    elif text.startswith('magnet'):
        pattern_res = re.findall('magnet:\?xt=urn:btih:[0-9a-fA-F]{40,}.*', text)
        for text in pattern_res:
            await client.add_uri(
                uris=[text],
            )
    elif event.media and event.media.document:
        if event.media.document.mime_type == 'application/x-bittorrent':
            await event.reply('收到了一个种子')
            path = await bot.download_media(event.message)
            await client.add_torrent(path)


def get_media_from_message(message: "Message") -> Any:
    media_types = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
    )
    for attr in media_types:
        media = getattr(message, attr, None)
        if media:
            return media


async def remove_all(event):
    # 过滤 已完成或停止
    tasks = await client.tell_stopped(0, 500)
    if len(tasks) == 0:
        await event.respond('没有要清空的任务', parse_mode='html')
        return
    for task in tasks:
        await client.remove_download_result(task['gid'])
    print('清空目录 ', tasks[0]['dir'])
    shutil.rmtree(tasks[0]['dir'], ignore_errors=True)

    await event.respond('任务已清空,所有文件已删除', parse_mode='html')


async def unpause_task(event):
    tasks = await client.tell_waiting(0, 50)
    # 筛选send_id对应的任务
    if len(tasks) == 0:
        await event.respond('没有已暂停的任务,无法恢复下载', parse_mode='markdown')
        return
    buttons = []
    for task in tasks:
        file_name = get_file_name(task)
        gid = task['gid']
        buttons.append([Button.inline(file_name, 'unpause-task.' + gid)])
    await event.respond('请选择要恢复▶️的任务', parse_mode='html', buttons=buttons)


async def remove_task(event):
    temp_task = []
    # 正在下载的任务
    tasks = await client.tell_active()
    for task in tasks:
        temp_task.append(task)
    # 正在等待的任务
    tasks = await  client.tell_waiting(0, 50)
    for task in tasks:
        temp_task.append(task)
    if len(temp_task) == 0:
        await event.respond('没有正在运行或等待的任务,无删除选项', parse_mode='markdown')
        return
    # 拼接所有任务
    buttons = []
    for task in temp_task:
        file_name = get_file_name(task)
        gid = task['gid']
        buttons.append([Button.inline(file_name, 'del-task.' + gid)])
    await event.respond('请选择要删除❌ 的任务', parse_mode='html', buttons=buttons)


async def stop_task(event):
    tasks = await client.tell_active()
    if len(tasks) == 0:
        await event.respond('没有正在运行的任务,无暂停选项,请先添加任务', parse_mode='markdown')
        return
    buttons = []
    for task in tasks:
        fileName = get_file_name(task)
        gid = task['gid']
        buttons.append([Button.inline(fileName, 'pause-task.' + gid)])

    await event.respond('请选择要暂停⏸️的任务', parse_mode='html', buttons=buttons)


async def downloading(event):
    tasks = await client.tell_active()
    if len(tasks) == 0:
        await event.respond('没有正在运行的任务', parse_mode='html')
        return
    send_msg = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = get_file_name(task)
        if fileName == '':
            continue
        prog = progress(int(totalLength), int(completedLength))
        size = byte2_readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))

        send_msg = send_msg + '任务名称: <b>' + fileName + '</b>\n进度: ' + prog + '\n大小: ' + size + '\n速度: ' + speed + '/s\n\n'
    if send_msg == '':
        await event.respond('个别任务无法识别名称，请使用aria2Ng查看', parse_mode='html')
        return
    await event.respond(send_msg, parse_mode='html')


async def waiting(event):
    tasks = await client.tell_waiting(0, 30)
    if len(tasks) == 0:
        await event.respond('没有正在等待的任务', parse_mode='markdown')
        return
    send_msg = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = get_file_name(task)
        prog = progress(int(totalLength), int(completedLength))
        size = byte2_readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))
        send_msg = send_msg + '任务名称: ' + fileName + '\n进度: ' + prog + '\n大小: ' + size + '\n速度: ' + speed + '\n\n'
    await event.respond(send_msg, parse_mode='html')


async def stoped(event):
    tasks = await client.tell_stopped(0, 30)
    if len(tasks) == 0:
        await event.respond('没有已完成或停止的任务', parse_mode='markdown')
        return
    send_msg = ''
    for task in reversed(tasks):
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = get_file_name(task)
        prog = progress(int(totalLength), int(completedLength))
        size = byte2_readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))
        send_msg = send_msg + '任务名称: ' + fileName + '\n进度: ' + prog + '\n大小: ' + size + '\n速度: ' + speed + '\n\n'
    await event.respond(send_msg, parse_mode='html')


@events.register(events.CallbackQuery)
async def BotCallbackHandler(event):
    d = str(event.data, encoding="utf-8")
    [type, gid] = d.split('.', 1)
    if type == 'pause-task':
        await client.pause(gid)
    elif type == 'unpause-task':
        await client.unpause(gid)
    elif type == 'del-task':
        data = await client.remove(gid)
        if 'error' in data:
            await bot.send_message(ADMIN_ID, data['error']['message'])
        else:
            await bot.send_message(ADMIN_ID, '删除成功')


def get_menu():
    return [
        [
            Button.text('⬇️正在下载', resize=True),
            Button.text('⌛️ 正在等待', resize=True),
            Button.text('✅ 已完成/停止', resize=True)
        ],
        [
            Button.text('⏸️暂停任务', resize=True),
            Button.text('▶️恢复任务', resize=True),
            Button.text('❌ 删除任务', resize=True),
        ],
        [
            Button.text('❌ ❌ 清空已完成/停止', resize=True),
            Button.text('关闭键盘', resize=True),
        ],
    ]


# 入口
async def main():
    await client.connect()
    bot.add_event_handler(BotCallbackHandler)
    bot_me = await bot.get_me()
    commands = [
        BotCommand(command="start", description='开始使用'),
        BotCommand(command="help", description='帮助'),
        BotCommand(command="web", description='ariaNg在线地址'),
    ]
    await bot(
        SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='',
            commands=commands
        )
    )
    log.info(f'{bot_me.username} bot启动成功...')


loop = asyncio.get_event_loop()
try:
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    pass
