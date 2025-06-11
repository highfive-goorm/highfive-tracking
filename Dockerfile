FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Seoul

RUN apt-get update && apt-get install -y --no-install-recommends tzdata curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 로컬의 app/ 디렉토리 전체를 컨테이너의 /app/app/ 디렉토리로 복사
COPY ./app ./app

RUN useradd --system --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8010

# CMD 명령어는 WORKDIR (/app) 에서 실행됨.
# "app.main:app"은 /app 디렉토리 내의 'app' 패키지(즉, /app/app 디렉토리)를 찾고,
# 그 안의 'main' 모듈(즉, /app/app/main.py)에서 'app' 객체를 찾음.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--log-level", "info", "--access-log"]