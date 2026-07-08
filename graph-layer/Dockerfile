FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config
COPY data ./data

ENV HOST=0.0.0.0
ENV PORT=8096
EXPOSE 8096

CMD ["python", "-m", "app.app"]
