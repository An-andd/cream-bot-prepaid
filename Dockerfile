FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# LibreOffice + Microsoft-compatible fonts for accurate DOCX → PDF conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-writer \
    fonts-dejavu \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fonts-freefont-ttf \
    fontconfig \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build the Jinja2 template from kunjii.docx at image build time
RUN python build_template.py

# Create the output directory for generated PDFs/DOCXs
RUN mkdir -p output

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000}"]
