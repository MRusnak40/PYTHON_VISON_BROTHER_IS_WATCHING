FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=local_ca \
    if [ -f /run/secrets/local_ca ]; then export PIP_CERT=/run/secrets/local_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY app ./app

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
