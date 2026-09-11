FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=scorpion.settings \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8080

CMD ["sh", "-c", "python manage.py migrate && python manage.py create_render_superuser && python manage.py collectstatic --noinput && gunicorn scorpion.wsgi:application --bind 0.0.0.0:${PORT} --workers 1 --threads 1 --timeout 120 --max-requests 300 --max-requests-jitter 30"]