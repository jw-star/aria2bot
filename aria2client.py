import os
from pprint import pprint

import ujson
from aioaria2 import Aria2WebsocketClient

from util import getFileName, order_moov, imgCoverFromFile

SEND_ID = int(os.getenv('SEND_ID'))
UP_TELEGRAM = os.getenv('UP_TELEGRAM', 'False') == 'True'


class Aria2Client:
    rpc_url = ''
    rpc_token = ''
    bot = None
    client = None
    bot = None

    def __init__(self, rpc_url, rpc_token, bot):
        self.rpc_url = rpc_url
        self.rpc_token = rpc_token
        self.bot = bot

    async def init(self):
        self.client: Aria2WebsocketClient = await Aria2WebsocketClient.new(self.rpc_url, token=self.rpc_token,
                                                                           loads=ujson.loads,
                                                                           dumps=ujson.dumps, )

    async def on_download_start(self, trigger, data):
        print(f"===========下载 开始 {data}")
        gid = data['params'][0]['gid']
        # 查询是否是绑定特征值的文件
        tellStatus = await self.client.tellStatus(gid)
        await self.bot.send_message(SEND_ID,
                                    f'{getFileName(tellStatus)} 任务已经开始下载... \n 对应路径: {tellStatus["dir"]}',
                                    parse_mode='html')

    async def on_download_pause(self, trigger, data):
        gid = data['params'][0]['gid']

        tellStatus = await self.client.tellStatus(gid)
        filename = getFileName(tellStatus)
        print('回调===>任务: ', filename, '暂停')
        # await bot.send_message(SEND_ID, filename + ' 任务已经成功暂停')

    async def on_download_complete(self, trigger, data):
        print(f"===========下载 完成 {data}")
        gid = data['params'][0]['gid']

        tellStatus = await self.client.tellStatus(gid)
        files = tellStatus['files']
        # 上传文件
        for file in files:
            path = file['path']
            await self.bot.send_message(SEND_ID,
                                        '下载完成===> ' + path,
                                        )
            # 发送文件下载成功的信息

            if UP_TELEGRAM:
                if '[METADATA]' in path:
                    os.unlink(path)
                    return
                print('开始上传,路径文件:' + path)
                msg = await self.bot.send_message(SEND_ID,
                                                  '上传中===> ' + path,
                                                  )

                async def callback(current, total):
                    # print("\r", '正在发送', current, 'out of', total,
                    #       'bytes: {:.2%}'.format(current / total), end="", flush=True)
                    # await bot.edit_message(msg, path + ' \n上传中 : {:.2%}'.format(current / total))
                    print(current / total)

                try:
                    # 单独处理mp4上传
                    if '.mp4' in path:

                        pat, filename = os.path.split(path)
                        await order_moov(path, pat + '/' + 'mo-' + filename)
                        # 截图
                        await imgCoverFromFile(path, pat + '/' + filename + '.jpg')
                        os.unlink(path)
                        await self.bot.send_file(SEND_ID,
                                                 pat + '/' + 'mo-' + filename,
                                                 thumb=pat + '/' + filename + '.jpg',
                                                 supports_streaming=True,
                                                 progress_callback=callback
                                                 )
                        await msg.delete()
                        os.unlink(pat + '/' + filename + '.jpg')
                        os.unlink(pat + '/' + 'mo-' + filename)
                    else:
                        await self.bot.send_file(SEND_ID,
                                                 path,
                                                 progress_callback=callback
                                                 )
                        await msg.delete()
                        os.unlink(path)

                except FileNotFoundError as e:
                    print('文件未找到')

    async def on_download_error(self, trigger, data):
        print(f"===========下载 错误 {data}")
        gid = data['params'][0]['gid']

        tellStatus = await self.client.tellStatus(gid)
        errorCode = tellStatus['errorCode']
        errorMessage = tellStatus['errorMessage']
        print('任务', gid, '错误码', errorCode, '错误信息：', errorMessage)
        if errorCode == '12':
            await self.bot.send_message(SEND_ID, ' 任务正在下载,请删除后再尝试')
        else:
            await self.bot.send_message(SEND_ID, errorMessage)

        pprint(tellStatus)
