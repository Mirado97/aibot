FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data static && \
    python -c "import urllib.request; urllib.request.urlretrieve('https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js', 'static/lw-charts.js')"

CMD ["python", "app.py"]
