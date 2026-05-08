FROM python:3.10-slim

# Install LibreOffice and Microsoft Fonts for perfect PDF conversion
# The fonts are REQUIRED so the template layout doesn't break
RUN echo "deb http://deb.debian.org/debian bookworm contrib non-free" > /etc/apt/sources.list.d/contrib.list && \
    apt-get update && \
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get install -y --no-install-recommends libreoffice ttf-mscorefonts-installer fontconfig && \
    fc-cache -f -v && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Gunicorn binding to the dynamic PORT provided by Render
CMD gunicorn -b 0.0.0.0:$PORT app:app
