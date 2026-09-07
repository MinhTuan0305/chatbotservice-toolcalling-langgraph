FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p logs

# Overridden per-service by docker-compose.yml (api_server vs socket_server)
CMD ["python", "-m", "app.api_server"]
