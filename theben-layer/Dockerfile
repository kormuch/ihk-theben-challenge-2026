FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY assets ./assets
COPY config ./config
COPY data/fixtures ./data/fixtures

ENV HOST=0.0.0.0
ENV PORT=8098
ENV THEBEN_LAYER_CONFIG=/app/config/runtime.json
ENV THEBEN_LOGO_PATH=/app/assets/logo_theben.jpg
EXPOSE 8098

CMD ["python", "-m", "app.app"]
