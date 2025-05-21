from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiosqlite

from accurecord_test import settings


async def connect() -> aiosqlite.Connection:
    conn = aiosqlite.connect(settings.DB_PATH, check_same_thread=False)
    # FIXME workaround https://github.com/omnilib/aiosqlite/issues/290#issuecomment-2578942071
    conn.daemon = True
    conn = await conn
    await conn.execute("pragma journal_mode=wal")

    return conn


async def web_connect() -> AsyncGenerator[aiosqlite.Connection, None]:
    conn = await connect()

    try:
        yield conn
    finally:
        await conn.close()
