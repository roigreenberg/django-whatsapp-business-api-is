FROM python:3.10

WORKDIR /app

ENV TZ=Asia/Jerusalem
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
