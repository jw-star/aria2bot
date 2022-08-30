import os
from enum import Enum

import ffmpy3
from urllib.parse import urlparse


class Status(Enum):
    active = '正在下载'
    waiting = '等待下载'
    paused = '暂停'
    error = '错误'
    complete = '完成'
    removed = '已删除'


def getEmByName(key):
    for v in Status:
        if v.name == key:
            return v.value


def hum_convert(value):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = 1024.0
    for i in range(len(units)):
        if (value / size) < 1:
            return "%.2f%s" % (value, units[i])
        value = value / size


async def imgCoverFromFile(input, output):
    # ffmpeg -i 001.jpg -vf 'scale=320:320'  001_1.jpg
    ff = ffmpy3.FFmpeg(
        inputs={input: None},
        outputs={output: ['-y', '-vframes', '1', '-loglevel', 'quiet']}
    )
    await ff.run_async()
    await ff.wait()


async def order_moov(input, output):
    # ffmpeg -i input.mp4 -movflags faststart -acodec copy -vcodec copy output.mp4
    ff = ffmpy3.FFmpeg(
        inputs={input: None},
        outputs={output: ['-y', '-movflags', 'faststart', '-acodec', 'copy', '-vcodec', 'copy', '-loglevel', 'quiet']}
    )
    await ff.run_async()
    await ff.wait()


def byte2Readable(size):
    '''
    auth: wangshengke@kedacom.com ；科达柯大侠
    递归实现，精确为最大单位值 + 小数点后三位
    '''

    def strofsize(integer, remainder, level):
        if integer >= 1024:
            remainder = integer % 1024
            integer //= 1024
            level += 1
            return strofsize(integer, remainder, level)
        else:
            return integer, remainder, level

    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    integer, remainder, level = strofsize(size, 0, 0)
    if level + 1 > len(units):
        level = -1
    return ('{}.{:>03d}{}'.format(integer, remainder, units[level]))


def progress(total_length, completed_length):
    if total_length != 0:
        return '{:.2f}%'.format(completed_length / total_length * 100)
    else:
        return "0"


def getFileName(task):
    if task.__contains__('bittorrent'):
        if task['bittorrent'].__contains__('info'):
            # bt下载
            return task['bittorrent']['info']['name']
        # bt元信息
        return task['files'][0]['path']
    filename = task['files'][0]['path'].split('/')[-1]
    if filename == '':
        pa = urlparse(task['files'][0]['uris'][0]['uri'])
        filename = os.path.basename(pa.path)
    return filename
