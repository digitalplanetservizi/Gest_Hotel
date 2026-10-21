FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 hotel \
    && useradd --uid 10001 --gid hotel --no-create-home hotel
COPY --chown=hotel:hotel backend/ ./
RUN mkdir -p /app/staticfiles && chown hotel:hotel /app/staticfiles
USER hotel
EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]

