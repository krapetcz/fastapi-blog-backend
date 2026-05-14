FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["/entrypoint.sh"]
