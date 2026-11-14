FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=10000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Render injects PORT at runtime (default 10000); app.py reads it.
EXPOSE 10000

CMD ["python", "app.py"]
