FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt ./

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 5000 8765

CMD ["sh", "-c", "python tts_server.py >/tmp/linuxscape-tts.log 2>&1 & exec python game.py"]
