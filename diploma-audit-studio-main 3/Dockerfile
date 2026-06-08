FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc g++ git libssl-dev libffi-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Mythril в отдельном venv (конфликт eth-hash с slither)
RUN python -m venv /opt/myth-venv && \
    /opt/myth-venv/bin/pip install --no-cache-dir mythril==0.24.8

ENV MYTHRIL_BIN=/opt/myth-venv/bin/myth

# Основные зависимости (slither + приложение)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true
