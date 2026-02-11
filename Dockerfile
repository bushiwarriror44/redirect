FROM python:3.9-slim
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY public/ ./public/

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:3914", "wsgi:app"]
