FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PORT=8091

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --upgrade setuptools wheel \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8091

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
