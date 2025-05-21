-- Table for ChargeOutgoing
CREATE TABLE IF NOT EXISTS charge (
    claim_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    charge_amount REAL NOT NULL,
    cpt_code TEXT NOT NULL,
    risk_score REAL NOT NULL
);

-- Table for Job
CREATE TABLE IF NOT EXISTS job (
    job_id INTEGER PRIMARY KEY NOT NULL, -- INTEGER PRIMARY KEY is auto-incrementing in SQLite
    is_done INTEGER NOT NULL -- SQLite stores booleans as 0 (false) or 1 (true)
);
