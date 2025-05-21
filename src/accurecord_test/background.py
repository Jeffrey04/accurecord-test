import asyncio
import queue
from contextlib import suppress
from threading import Event
from typing import Any

import aiosqlite

from accurecord_test import database, settings
from accurecord_test.common import get_logger
from accurecord_test.web import ChargeIncoming, Job


def calculate_risk_score(amount: float) -> float:
    return round(amount / 1000, 2)


async def message_consume(conn: aiosqlite.Connection, logger: Any) -> None:
    try:
        while True:
            try:
                # NOTE: Setting timeout is crucial to allow application to shutdown gracefully
                payload = await asyncio.to_thread(
                    settings.incoming_queue.get, timeout=settings.QUEUE_TIMEOUT
                )
            except queue.Empty:
                continue

            logger.info("Received job", job=payload["job"].job_id)

            await process_payload(conn, payload, logger)
    except asyncio.CancelledError:
        logger.info("Exiting")
        pass


async def process_payload(
    conn: aiosqlite.Connection,
    payload: dict[str, Job | list[ChargeIncoming]],
    logger: Any,
):
    async with conn.cursor() as cursor:
        try:
            for charge in payload["data"]:  # type: ignore
                logger.info(
                    "Writing charge",
                    job=payload["job"].job_id,
                    claim_id=charge.claim_id,
                )
                await cursor.execute(
                    """
                            INSERT
                            INTO    charge (claim_id, patient_id, charge_amount, cpt_code, risk_score)
                            VALUES  (?, ?, ?, ?, ?)
                            """,
                    (
                        charge.claim_id,
                        charge.patient_id,
                        charge.charge_amount,
                        charge.cpt_code,
                        calculate_risk_score(charge.charge_amount),
                    ),
                )

            await cursor.execute(
                """
                        UPDATE  job
                        SET     is_done = TRUE
                        WHERE   job_id = ?
                        """,
                (payload["job"].job_id,),  # type: ignore
            )
        except Exception as e:
            logger.exception(e)
            raise e

    await conn.commit()


async def run(exit_event: Event):
    logger = get_logger(__name__)

    logger.info("BG: Starting up")
    conn = database.connect()

    logger.info("BG: Ready for requests")
    task = asyncio.create_task(message_consume(conn, logger))

    await asyncio.to_thread(exit_event.wait)

    logger.info("BG: Exiting")
    task.cancel()
