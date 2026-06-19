FROM python:3.13-slim

WORKDIR /app

# Dipendenze (audioop-lts ha wheel manylinux per cp313)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codice applicativo + dati dei tenant (listino, prompt)
COPY app ./app
COPY tenants ./tenants

# Cloud Run inietta la porta via $PORT (default 8080). uvicorn ascolta su 0.0.0.0.
ENV PORT=8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
