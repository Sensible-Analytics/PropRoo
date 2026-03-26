FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for local data files
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data

EXPOSE 8000

# Use shell form to ensure environment variables are available
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000
