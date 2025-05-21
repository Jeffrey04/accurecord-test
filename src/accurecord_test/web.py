import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from threading import Event
from typing import Any, Self

import aiosqlite
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from starlette import status

from accurecord_test import database, settings
from accurecord_test.common import get_logger, get_web_logger

app = FastAPI()


@dataclass
class ChargeIncoming:
    claim_id: str
    patient_id: str
    charge_amount: float
    cpt_code: str


@dataclass
class ChargeOutgoing:
    claim_id: str
    patient_id: str
    charge_amount: float
    cpt_code: str
    risk_score: float

    @classmethod
    def factory(cls, cur: aiosqlite.Cursor, row: Sequence[Any]) -> Self:
        return cls(*row)


@dataclass
class Job:
    job_id: int
    is_done: bool

    @classmethod
    def factory(cls, cur: aiosqlite.Cursor, row: Sequence[Any]) -> Self:
        return cls(row[0], bool(row[1]))


@app.post("/charges/batch")
async def claim_submit(
    charges: list[ChargeIncoming],
    conn: aiosqlite.Connection = Depends(database.web_connect),
    logger: Any = Depends(get_web_logger(__name__)),
) -> Job:
    await conn.execute("BEGIN")
    async with conn.cursor() as cursor:
        cursor.row_factory = Job.factory

        await cursor.execute(
            """
            INSERT
            INTO        job (is_done)
            VALUES      (FALSE)
            RETURNING   job_id, is_done
            """
        )

        job = await cursor.fetchone()

    await conn.commit()

    await asyncio.to_thread(settings.incoming_queue.put, {"job": job, "data": charges})

    return job  # type: ignore


@app.get("/charges/job/{job_id}")
async def job_get_status(
    job_id: int,
    conn: aiosqlite.Connection = Depends(database.web_connect),
    logger=get_web_logger(__name__),
) -> Job:
    async with conn.cursor() as cursor:
        cursor.row_factory = Job.factory  # type: ignore

        await cursor.execute(
            """
            SELECT  job_id, is_done
            FROM    job
            WHERE   job_id = ?
            """,
            (job_id,),
        )

        if result := await cursor.fetchone():
            return result  # type: ignore
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} is not found",
            )


@app.get("/charges/{claim_id}")
async def claim_get(
    claim_id: str, conn: aiosqlite.Connection = Depends(database.web_connect)
) -> ChargeOutgoing:
    async with conn.cursor() as cursor:
        cursor.row_factory = ChargeOutgoing.factory  # type: ignore

        await cursor.execute(
            """
            SELECT  claim_id, patient_id, charge_amount, cpt_code, risk_score
            FROM    charge
            WHERE   claim_id = ?
            """,
            (claim_id,),
        )

        if result := await cursor.fetchone():
            return result  # type: ignore
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Charge with claim_id={claim_id} is not found",
            )


async def run(exit_event: Event, logger=get_logger(__name__)) -> None:
    server = uvicorn.Server(
        uvicorn.Config(
            "accurecord_test.web:app",
            host="0.0.0.0",
            port=settings.WEB_PORT,
            log_level="info",
        )
    )

    logger.info("WEB: Starting")
    asyncio.create_task(server.serve())

    logger.info("WEB: Ready for requests")

    await asyncio.to_thread(exit_event.wait)

    logger.info("WEB: Stopping")

    await server.shutdown()
