FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements
COPY requirements.txt .

# Installa dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia gli script ETL
COPY *.py ./

# Crea directory per lo stato persistente
RUN mkdir -p /app/state

# Volume per stato persistente
VOLUME ["/app/state"]

# Default command (può essere sovrascritto in docker-compose)
CMD ["python", "-u", "extract_from_thingsboard.py"]
