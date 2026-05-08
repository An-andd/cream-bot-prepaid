FROM python:3.10-slim

# Install LibreOffice for PDF conversion
RUN apt-get update && apt-get install -y libreoffice && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]
