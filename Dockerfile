FROM python:3.11-slim

# Tesseract runs fully offline. Build needs network once; runtime does not.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
COPY src ./src
COPY tests ./tests

EXPOSE 8000
CMD ["uvicorn", "usreport.server:app", "--host", "0.0.0.0", "--port", "8000"]
