ARG PYTHON_BASE_IMAGE=python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /agents

COPY app ./app
COPY config ./config
COPY tests ./tests
COPY scripts ./scripts

RUN chmod +x /agents/scripts/validate.sh

EXPOSE 8090
CMD ["python3", "-m", "app.app", "--host", "0.0.0.0", "--port", "8090"]
