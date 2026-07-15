FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir \
        -r /app/requirements.txt

COPY . /app

RUN mkdir -p \
        /app/staticfiles \
        /app/media \
        /app/logs \
        /app/knowledge_base/vector_store

# Build-only placeholder values.
# Do not place real production secrets here.
RUN DJANGO_SECRET_KEY=django-build-only-placeholder \
    DJANGO_DEBUG=False \
    DJANGO_ALLOWED_HOSTS="*" \
    LEGAL_GUIDANCE_INTERNAL_API_KEY=legal-build-only-placeholder \
    OPENAI_API_KEY=sk-build-only-placeholder \
    TAVILY_ENABLED=False \
    python manage.py collectstatic --noinput

RUN useradd \
        --create-home \
        --shell /bin/bash \
        appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 300 --access-logfile - --error-logfile - --capture-output"]