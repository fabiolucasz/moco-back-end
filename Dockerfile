FROM python:3.12-slim

COPY . /app

WORKDIR /app
RUN pip install uv
RUN uv sync

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["/app/entrypoint.sh"]
