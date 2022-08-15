import asyncio
import os
import shutil

import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import datetime
from pprint import pprint

import aioaria2
import socks
import ujson
from telethon import TelegramClient, events, Button
from util import *


API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
JSON_RPC_URL = os.getenv('JSON_RPC_URL')
JSON_RPC_TOKEN = os.getenv('JSON_RPC_TOKEN')
UP_TELEGRAM = os.getenv('UP_TELEGRAM', 'False') == 'True'
SEND_ID = int(os.getenv('SEND_ID'))
# 可选配置
PROXY_IP = os.getenv('PROXY_IP', None)
PROXY_PORT = os.getenv('PROXY_PORT', None)

if PROXY_PORT is None or PROXY_IP is None:
    proxy = None
else:
    proxy = (socks.HTTP, PROXY_IP, int(PROXY_PORT))

bot = TelegramClient(None, API_ID, API_HASH, proxy=proxy).start(bot_token=BOT_TOKEN)

client = None


# 入口
async def main():
    global client
    await initClient()
    bot.add_event_handler(BotCallbackHandler)
    print('bot启动了')


# 内联按钮回调===============
@events.register(events.CallbackQuery)
async def BotCallbackHandler(event):
    # 按钮点击后的回调
    # print(event.data)
    d = str(event.data, encoding="utf-8")
    [type, gid] = d.split('.', 1)
    if type == 'pause-task':
        await pause(event, gid)
    elif type == 'unpause-task':
        await unpause(event, gid)
    elif type == 'del-task':
        await delToTask(event, gid)


# 消息监听开始===============
@bot.on(events.NewMessage(pattern='/menu'))
async def send_welcome(event):
    # menu
    menu = [
        [
            Button.text('⬇️正在下载'),
            Button.text('⌛️ 正在等待'),
            Button.text('✅ 已完成/停止')
        ],
        [
            Button.text('⏸️暂停任务'),
            Button.text('▶️恢复任务'),
            Button.text('❌ 删除任务'),
        ],
        [
            Button.text('❌ ❌ 清空已完成/停止'),
            Button.text('关闭键盘'),
        ],
    ]

    await event.respond('请选择一个选项', parse_mode='html', buttons=menu)


@bot.on(events.NewMessage(pattern="/close"))
async def handler(event):
    await event.reply("键盘已关闭", buttons=Button.clear())


@bot.on(events.NewMessage(pattern="/start"))
async def handler(event):
    await event.reply("aria2控制机器人,点击复制你的send_id:<code>%s</code>" % (str(event.chat_id)), parse_mode='html')


@bot.on(events.NewMessage)
async def send_welcome(event):
    text = event.raw_text
    print(str(datetime.datetime.now()) + ':' + text)

    # 键盘消息
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
        await stopTask(event)
        return
    elif text == '▶️恢复任务':
        await unstopTask(event)
        return
    elif text == '❌ 删除任务':
        await removeTask(event)
        return
    elif text == '❌ ❌ 清空已完成/停止':
        await removeAll(event)
        return
    elif text == '关闭键盘':
        await event.reply("键盘已关闭,/menu 开启键盘", buttons=Button.clear())
        return
    # http 磁力链接
    if text.startswith('http') or text.startswith('magnet:?'):
        global client
        if client is None or client.closed:
            # 重启客户端
            await initClient()
        if text.endswith('.mp4'):
            mp4Name = text.split('/')[-1]
            gid = await client.addUri(
                [text],
                options={'out': mp4Name}
            )
        else:
            gid = await client.addUri(
                [text],
            )

    try:
        if event.media and event.media.document:
            print(event.media.document.mime_type)
            if event.media.document.mime_type == 'application/x-bittorrent':
                print('收到了一个种子')
                await event.reply('收到了一个种子')
                path = await bot.download_media(event.message)
                print(path)
                global client
                if client is None or client.closed:
                    # 重启客户端
                    await initClient()
                gid = await client.add_torrent(path)
                print(gid)
                os.unlink(path)
    except Exception as e:
        pass


# 消息监听结束===============


async def initClient():
    global client
    client = await aioaria2.Aria2WebsocketClient.new(JSON_RPC_URL,
                                                     token=JSON_RPC_TOKEN,
                                                     loads=ujson.loads,
                                                     dumps=ujson.dumps)
    client.onDownloadComplete(on_download_complete)
    client.onDownloadError(on_download_error)
    # client.onBtDownloadComplete(on_download_complete)
    client.onDownloadStart(on_download_start)
    client.onDownloadPause(on_download_pause)


# rpc回调开始==========================
async def on_download_start(trigger, data):
    print(f"===========下载 开始 {data}")
    gid = data['params'][0]['gid']
    global client
    # 查询是否是绑定特征值的文件
    tellStatus = await client.tellStatus(gid)
    await bot.send_message(SEND_ID, getFileName(tellStatus) + ' 任务已经开始下载')


async def on_download_complete(trigger, data):
    print(f"===========下载 完成 {data}")
    gid = data['params'][0]['gid']
    global client
    tellStatus = await client.tellStatus(gid)
    files = tellStatus['files']
    if UP_TELEGRAM:
        # 上传文件
        for file in files:
            path = file['path']

            if '[METADATA]' in path:
                os.unlink(path)
                return
            print('开始上传,路径文件:' + path)
            msg = await bot.send_message(SEND_ID,
                                         '上传中===> ' + path,
                                         )

            async def callback(current, total):
                print("\r", '正在发送', current, 'out of', total,
                      'bytes: {:.2%}'.format(current / total), end="", flush=True)
                # await bot.edit_message(msg, path + ' \n上传中 : {:.2%}'.format(current / total))

            try:
                # 单独处理mp4上传
                if '.mp4' in path:

                    pat, filename = os.path.split(path)
                    await order_moov(path, pat + '/' + 'mo-' + filename)
                    # 截图
                    await imgCoverFromFile(path, pat + '/' + filename + '.jpg')
                    os.unlink(path)
                    await bot.send_file(SEND_ID,
                                        pat + '/' + 'mo-' + filename,
                                        thumb=pat + '/' + filename + '.jpg',
                                        supports_streaming=True,
                                        progress_callback=callback
                                        )
                    os.unlink(pat + '/' + filename + '.jpg')
                    os.unlink(pat + '/' + 'mo-' + filename)
                else:
                    await bot.send_file(SEND_ID,
                                        path,
                                        progress_callback=callback
                                        )
                    await msg.delete()
                    os.unlink(path)

            except FileNotFoundError:
                pass


async def on_download_pause(trigger, data):
    gid = data['params'][0]['gid']
    global client
    tellStatus = await client.tellStatus(gid)
    filename = getFileName(tellStatus)
    print('回调===>任务: ', filename, '暂停')
    await bot.send_message(SEND_ID, filename + ' 任务已经成功暂停')


async def on_download_error(trigger, data):
    print(f"===========下载 错误 {data}")
    gid = data['params'][0]['gid']
    global client
    tellStatus = await client.tellStatus(gid)
    errorCode = tellStatus['errorCode']
    errorMessage = tellStatus['errorMessage']
    print('任务', gid, '错误码', errorCode, '错误信息：', errorMessage)
    if errorCode == '12':
        await bot.send_message(SEND_ID, ' 任务正在下载,请删除后再尝试')
    else:
        await bot.send_message(SEND_ID, errorMessage)

    pprint(tellStatus)


# rpc回调结束=================================


# 文本按钮回调方法=============================
async def downloading(event):
    global client
    tasks = await client.tellActive()
    if len(tasks) == 0:
        await event.respond('没有正在运行的任务', parse_mode='markdown')
        return

    send_str = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = getFileName(task)
        prog = progress(int(totalLength), int(completedLength))
        size = byte2Readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))

        send_str = send_str + '任务名称: <b>' + fileName + '</b>\n进度: ' + prog + '\n大小: ' + size + '\n速度: ' + speed + '/s\n\n'
    await event.respond(send_str, parse_mode='html')


async def waiting(event):
    global client
    tasks = await client.tellWaiting(0, 10)
    # 筛选send_id对应的正在下载任务
    if len(tasks) == 0:
        await event.respond('没有正在等待的任务', parse_mode='markdown')
        return
    send_str = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = getFileName(task)
        prog = progress(int(totalLength), int(completedLength))
        size = byte2Readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))

        send_str = send_str + '任务名称: ' + fileName + '\n进度: ' + prog + '\n大小: ' + size + '\n速度: ' + speed + '\n\n'
    await event.respond(send_str, parse_mode='html')


async def stoped(event):
    global client
    tasks = await  client.tellStopped(0, 500)

    if len(tasks) == 0:
        await event.respond('没有已完成或停止的任务', parse_mode='markdown')
        return
    send_str = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = getFileName(task)
        prog = progress(int(totalLength), int(completedLength))
        size = byte2Readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))

        send_str = send_str + '任务名称: ' + fileName + '\n进度: ' + prog + '\n大小: ' + size + '\n速度: ' + speed + '\n\n'
    await event.respond(send_str, parse_mode='html')


async def stopTask(event):
    global client
    tasks = await client.tellActive()

    # 筛选send_id对应的正在下载任务
    if len(tasks) == 0:
        await event.respond('没有正在运行的任务,无暂停选项,请先添加任务', parse_mode='markdown')
        return
    # 拼接所有任务
    buttons = []
    for task in tasks:
        fileName = getFileName(task)
        gid = task['gid']
        buttons.append(Button.inline(fileName, 'pause-task.' + gid))

    await event.respond('请选择要暂停⏸️的任务', parse_mode='html', buttons=buttons)


async def unstopTask(event):
    global client
    tasks = await client.tellWaiting(0, 500)
    # 筛选send_id对应的任务
    if len(tasks) == 0:
        await event.respond('没有已暂停的任务,无法恢复下载', parse_mode='markdown')
        return
    buttons = []
    for task in tasks:
        fileName = getFileName(task)
        gid = task['gid']
        buttons.append(Button.inline(fileName, 'unpause-task.' + gid))

    await event.respond('请选择要恢复▶️的任务', parse_mode='html', buttons=buttons)


async def removeTask(event):
    global client

    tempTask = []
    # 正在下载的任务
    tasks = await client.tellActive()
    for task in tasks:
        tempTask.append(task)
    # 正在等待的任务
    tasks = await client.tellWaiting(0, 1000)
    for task in tasks:
        tempTask.append(task)
    if len(tempTask) == 0:
        await event.respond('没有正在运行或等待的任务,无删除选项', parse_mode='markdown')
        return

    # 拼接所有任务
    buttons = []
    for task in tempTask:
        fileName = getFileName(task)
        gid = task['gid']
        buttons.append(Button.inline(fileName, 'del-task.' + gid))
    await event.respond('请选择要删除❌ 的任务', parse_mode='html', buttons=buttons)


async def removeAll(event):
    global client
    # 过滤 已完成或停止
    tasks = await  client.tellStopped(0, 500)

    if len(tasks) == 0:
        await event.respond('没有要清空的任务', parse_mode='html')
        return

    for task in tasks:
        await client.removeDownloadResult(task['gid'])
        dir = task['dir']

    try:
        print('清空目录 ', dir)
        shutil.rmtree(dir, ignore_errors=True)
    except Exception as e:
        print(e)
        pass
    await event.respond('任务已清空,所有文件已删除', parse_mode='html')


# 文本按钮回调方法结束=============================


# 调用暂停
async def pause(event, gid):
    global client
    await client.pause(gid)


# 调用恢复
async def unpause(event, gid):
    global client
    await client.unpause(gid)


# 调用删除
async def delToTask(event, gid):
    global client
    await client.remove(gid)
    await bot.send_message(SEND_ID, '任务删除成功')


loop = asyncio.get_event_loop()
try:
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    pass
