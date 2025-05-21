from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiosqlite

from accurecord_test import settings


async def connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(settings.DB_PATH, check_same_thread=False)
    await conn.execute("pragma journal_mode=wal")

    return conn


async def web_connect() -> AsyncGenerator[aiosqlite.Connection, None]:
    conn = await connect()

    try:
        yield conn
    finally:
        await conn.close()
