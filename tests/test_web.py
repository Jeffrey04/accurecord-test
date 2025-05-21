import json

import aiosqlite
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from accurecord_test import settings
from accurecord_test.database import web_connect
from accurecord_test.web import app


@pytest_asyncio.fixture(name="connection")
async def db_fixture():
    conn = aiosqlite.connect(":memory:")
    conn.daemon = True
    conn = await conn

    with open("./database/schema.sql") as f:
        await conn.executescript(f.read())  # type: ignore

    await conn.commit()

    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture(name="client")
def client_fixture(connection: aiosqlite.Connection):
    async def _db():
        yield connection

    app.dependency_overrides[web_connect] = _db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_job(
    client: TestClient,
    connection: aiosqlite.Connection,
):
    with open("./data.json") as f:
        batch = json.load(f)
        response = client.post("/charges/batch", json=batch)

    assert response.status_code == 200

    data = response.json()
    assert "job_id" in data
    assert data["is_done"] is False

    # check if the job is written to the database
    async with connection.cursor() as cursor:
        cursor = await cursor.execute(
            "SELECT job_id, is_done from job WHERE job_id = ?", (data["job_id"],)
        )
        result = await cursor.fetchone()

    assert result is not None
    assert result[0] == data["job_id"]
    assert result[1] == data["is_done"]

    # check if the job is sent to the queue
    payload = settings.incoming_queue.get()

    assert data["job_id"] == payload["job"].job_id
    assert data["is_done"] == payload["job"].is_done

    for idx, charge in enumerate(batch):
        assert charge["claim_id"] == payload["data"][idx].claim_id
        assert charge["patient_id"] == payload["data"][idx].patient_id
        assert charge["charge_amount"] == payload["data"][idx].charge_amount
        assert charge["cpt_code"] == payload["data"][idx].cpt_code


def test_check_job(client: TestClient):
    response = client.get("/charges/job/1")

    # should return 404 as no record is in the database
    assert response.status_code == 404

    # now let's write something into the database
    with open("./data.json") as f:
        response = client.post("/charges/batch", json=json.load(f))

    job = response.json()

    response = client.get(f"charges/job/{job['job_id']}")

    data = response.json()

    assert job["job_id"] == data["job_id"]
    assert job["is_done"] == data["is_done"]


@pytest.mark.asyncio
async def test_check_charge(
    client: TestClient,
    connection: aiosqlite.Connection,
):
    response = client.get("/charges/CLAIM010")

    assert response.status_code == 404

    data = {
        "claim_id": "CLAIM003",
        "patient_id": "PAT001",
        "charge_amount": 450.25,
        "cpt_code": "99211",
        "risk_score": 1.0,
    }

    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            INSERT
            INTO    charge (claim_id, patient_id, charge_amount, cpt_code, risk_score)
            VALUES  (?, ?, ?, ?, ?)
            """,
            (
                data["claim_id"],
                data["patient_id"],
                data["charge_amount"],
                data["cpt_code"],
                data["risk_score"],
            ),
        )
    await connection.commit()

    response = client.get(f"/charges/{data['claim_id']}")

    assert response.status_code == 200

    charge = response.json()

    assert data["claim_id"] == charge["claim_id"]
    assert data["patient_id"] == charge["patient_id"]
    assert data["charge_amount"] == charge["charge_amount"]
    assert data["cpt_code"] == charge["cpt_code"]
    assert data["risk_score"] == charge["risk_score"]
