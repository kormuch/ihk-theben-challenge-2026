FROM python:3.12-slim

WORKDIR /app
COPY . /app
EXPOSE 8095
CMD ["python3", "-B", "app/app.py", "--host", "0.0.0.0", "--port", "8095"]
