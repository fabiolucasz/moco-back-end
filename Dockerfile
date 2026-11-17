FROM python:3.12-slim

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app
WORKDIR /app

RUN uv sync --no-dev

EXPOSE 8000
CMD ["sh", "/app/entrypoint.sh"]
