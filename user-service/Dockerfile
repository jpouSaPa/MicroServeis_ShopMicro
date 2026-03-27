FROM python:3.12-slim

# Security: no root in production
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app.py .

# Ownership
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 5002

ENV FLASK_DEBUG=false \
    SECRET_KEY=change-me-in-production \
    DATABASE_URL=sqlite:///users.db \
    JWT_EXPIRATION_HOURS=24

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", "--timeout", "60", "app:app"]
