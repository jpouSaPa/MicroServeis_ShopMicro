# ~/shopmicro/product-service/Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Dependencies needed to compile mysqlclient
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5003
CMD ["python", "app.py"]
