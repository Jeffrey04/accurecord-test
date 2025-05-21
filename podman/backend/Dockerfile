FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y sqlite3 && \
    uv sync --frozen --no-editable --no-dev --compile-bytecode && \
    # distroless's cpython is in /usr/bin/python
    #rm /app/.venv/bin/python && \
    #ln -s /usr/bin/python /app/.venv/bin/python && \
    touch database.sqlite && \
    sqlite3 database.sqlite < database/schema.sql

EXPOSE 8081/tcp

ENTRYPOINT ["/app/.venv/bin/accurecord-test"]

#FROM gcr.io/distroless/python3-debian12:debug
#
#EXPOSE 8081/tcp
#
#COPY --from=builder /app/.venv /app/.venv
#COPY --from=builder /app/database.sqlite /app/database.sqlite
#
#ENTRYPOINT ["/app/.venv/bin/accurecord-test"]