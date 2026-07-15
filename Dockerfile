# Dockerfile for django-ai-service

FROM python:3.12-slim

# Prevent Python from creating .pyc files and buffer-free logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install system packages required by common Python dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first to improve Docker layer caching.
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

# Copy the Django project.
COPY . /app

# Create directories that Django may need.
RUN mkdir -p \
        /app/staticfiles \
        /app/media \
        /app/logs

# Collect static files during the image build.
# The temporary secret is used only for this build command.
RUN DJANGO_SECRET_KEY=temporary-build-secret \
    DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

# Create a non-root runtime user.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Cloud Run automatically provides the PORT environment variable.
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 300 --access-logfile - --error-logfile - --capture-output"]