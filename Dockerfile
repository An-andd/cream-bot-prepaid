FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Gunicorn binding to the dynamic PORT provided by Render
CMD gunicorn -b 0.0.0.0:$PORT app:app
