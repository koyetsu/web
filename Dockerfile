FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEBROOT_PATH=/webroot \
    FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    ADMIN_PASSWORD=printstudio

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

VOLUME ["/webroot"]

EXPOSE 5000

CMD ["flask", "run", "--port=5000"]
