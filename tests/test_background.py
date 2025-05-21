import asyncio
import json
import multiprocessing
from operator import itemgetter

import aiosqlite
import pytest
import pytest_asyncio

from accurecord_test.background import calculate_risk_score, message_consume
from accurecord_test.common import get_logger
from accurecord_test.web import ChargeIncoming, Job


@pytest_asyncio.fixture(name="connection")
async def db_fixture():
    conn = await aiosqlite.connect(":memory:")

    with open("./database/schema.sql") as f:
        await conn.executescript(f.read())  # type: ignore

    await conn.commit()

    return conn


@pytest.mark.asyncio
async def test_message_consume(
    connection: aiosqlite.Connection,
    session_multiprocessing_queue: multiprocessing.Queue,
):
    async with connection.cursor() as cursor:
        cursor.row_factory = aiosqlite.Row

        await cursor.execute(
            """
            INSERT
            INTO        job (is_done)
            VALUES      (FALSE)
            RETURNING   job_id, is_done
            """
        )
        job = await cursor.fetchone()

        assert job is not None

        with open("./data.json") as f:
            charges = sorted(json.load(f), key=itemgetter("claim_id"))

            session_multiprocessing_queue.put(
                {
                    "job": Job(job["job_id"], bool(job["is_done"])),
                    "data": [
                        ChargeIncoming(
                            charge["claim_id"],
                            charge["patient_id"],
                            charge["charge_amount"],
                            charge["cpt_code"],
                        )
                        for charge in charges
                    ],
                }
            )

        task = asyncio.create_task(message_consume(connection, get_logger(__name__)))

        await asyncio.sleep(1)
        task.cancel()

        # check if data is inserted
        await cursor.execute(
            """
            SELECT      *
            FROM        charge
            ORDER BY    claim_id
            """
        )

        idx = 0
        async for charge in cursor:
            assert charge["claim_id"] == charges[idx]["claim_id"]
            assert charge["patient_id"] == charges[idx]["patient_id"]
            assert charge["charge_amount"] == charges[idx]["charge_amount"]
            assert charge["cpt_code"] == charges[idx]["cpt_code"]
            assert charge["risk_score"] == round(
                charges[idx]["charge_amount"] / 1000, 2
            )

            idx += 1

        assert idx != 0

        await cursor.execute(
            """
            SELECT  *
            FROM    job
            WHERE   job_id = ?
            """,
            (job["job_id"],),
        )
        job_updated = await cursor.fetchone()

        assert job_updated is not None
        assert bool(job_updated["is_done"]) is True


def test_calculate_risk_score(connection: aiosqlite.Connection):
    assert calculate_risk_score(1111) == round(1111 / 1000, 2)
    assert calculate_risk_score(7077) == round(7077 / 1000, 2)
