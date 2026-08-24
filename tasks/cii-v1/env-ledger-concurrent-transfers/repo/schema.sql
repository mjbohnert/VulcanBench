CREATE TABLE IF NOT EXISTS accounts (
    id      TEXT PRIMARY KEY,
    balance BIGINT NOT NULL CHECK (balance >= 0)
);

CREATE TABLE IF NOT EXISTS events (
    id      TEXT PRIMARY KEY,
    account TEXT NOT NULL REFERENCES accounts (id),
    delta   BIGINT NOT NULL
);
