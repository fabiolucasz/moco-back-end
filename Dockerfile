FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /uvx /bin/

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies (without dev dependencies for production)
RUN uv pip install --system -e .

# Copy source code
COPY . .

# Create entrypoint script
RUN echo '#!/bin/sh\nalembic upgrade head\nexec uvicorn src.main:app --host 0.0.0.0 --port 8000' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
