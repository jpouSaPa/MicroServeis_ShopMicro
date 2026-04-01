FROM python:3.12-slim

# --- Install system dependencies required for cryptography ---
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Security: no root in production
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app.py .

# Ownership
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 5002

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "4", "--timeout", "120", "app:app"]
