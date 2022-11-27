#pip install pipreqs
#pipreqs requirements.txt
FROM python:3.10.7-slim-buster

RUN apt-get update && apt-get -y install  gcc ffmpeg
COPY . /app
RUN python -m pip install --upgrade pip && pip3 --no-cache-dir install --user -r /app/requirements.txt
WORKDIR /app
# -u print打印出来
CMD ["python3", "-u", "bot.py"]
