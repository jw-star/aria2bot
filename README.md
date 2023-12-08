# ariabot

aria2 telegram bot

### 特点

1. 基于电报机器人控制aria2，自行设置下载完成后是否上传telegram
2. ~~多用户，每个用户只能看到自己的任务~~，单用户现在，多用户没什么用
3. 支持 `批量` 添加 http、磁力、种子下载
4. 支持自定义目录下载,使用 /path 命令设置
5. 自己实现 `aria2c` `jsonrpc` 调用 增加断开重连功能
6. 命令 /web 获取在线 ariaNg web控制地址，方便跳转
7. 下载实时进度、上传实时进度显示

### 缺点

1. 由于电报单个文件2G限制,超过2g文件将上传失败,可以使用手机号登陆方式去实现会员最大4g文件上传

### 如何安装

1.重命名 db/config.example.yml 为 config.yml

设置参数
```yaml
API_ID: xxxx
API_HASH: xxxxxxxx
BOT_TOKEN: xxxx:xxxxxxxxxxxx
ADMIN_ID: 管理员ID
#默认是否上传到电报 true 或者 false
UP_TELEGRAM: true
#aria2c 设置
RPC_SECRET: xxxxxxx
RPC_URL: xxxxxx:6800/jsonrpc

#代理ip 不需要留空,目前代理只支持代理bot，aria2c 连接不支持代理目前
PROXY_IP: 
PROXY_PORT:
```

2.启动

安装 docker

```
curl -fsSL get.docker.com -o get-docker.sh&&sh get-docker.sh &&systemctl enable docker&&systemctl start docker
```

下载库到本地

```bash
git clone https://github.com/jw-star/aria2bot.git
```

删除容器（如果容器存在）

```
docker compose down
```

后台启动

```yaml
docker compose up -d --build
```

查看日志

```yaml
docker compose logs -f --tail=4000
```

### 自行安装aria2

aria2 一键安装脚本

```yaml
https://github.com/P3TERX/aria2.sh
```

### 应用截图

/help 查看帮助

<img alt="img.png" height="400" src="./img.png" />

### 灵感来自

https://github.com/HouCoder/tele-aria2

多平台构建参考: https://cloud.tencent.com/developer/article/1543689

