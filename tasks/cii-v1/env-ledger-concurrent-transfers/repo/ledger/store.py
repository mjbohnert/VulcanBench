"""The ledger: transfers, idempotent event application, and cached balances.

Money conservation is the core invariant: a transfer moves `amount` from one
account to another, rejecting overdrafts. Events apply exactly once per event
id. `cached_balance` serves reads through the Redis cache.
"""

from ledger.db import Redis, pg_connect


class InsufficientFunds(Exception):
    pass


def balance(account: str) -> int:
    with pg_connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT balance FROM accounts WHERE id = %s", (account,))
        row = cur.fetchone()
        if row is None:
            raise KeyError(account)
        return int(row[0])


def transfer(src: str, dst: str, amount: int) -> None:
    if amount <= 0:
        raise ValueError("amount must be positive")
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM accounts WHERE id = %s", (src,))
            src_balance = int(cur.fetchone()[0])
            # Prime the cache with the outcome so readers see it immediately.
            cache = Redis()
            cache.set(f"balance:{src}", str(src_balance - amount))
            cache.close()
            if src_balance < amount:
                raise InsufficientFunds(src)
            cur.execute("SELECT balance FROM accounts WHERE id = %s", (dst,))
            dst_balance = int(cur.fetchone()[0])
            cur.execute(
                "UPDATE accounts SET balance = %s WHERE id = %s",
                (src_balance - amount, src),
            )
            cur.execute(
                "UPDATE accounts SET balance = %s WHERE id = %s",
                (dst_balance + amount, dst),
            )
        conn.commit()
    finally:
        conn.close()


def apply_event(event_id: str, account: str, delta: int) -> bool:
    """Apply a balance event exactly once. Returns True when this call applied it."""
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM events WHERE id = %s", (event_id,))
            if cur.fetchone() is not None:
                return False
            cur.execute(
                "INSERT INTO events (id, account, delta) VALUES (%s, %s, %s)",
                (event_id, account, delta),
            )
            cur.execute("SELECT balance FROM accounts WHERE id = %s", (account,))
            current = int(cur.fetchone()[0])
            cur.execute(
                "UPDATE accounts SET balance = %s WHERE id = %s",
                (current + delta, account),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def cached_balance(account: str) -> int:
    cache = Redis()
    try:
        hit = cache.get(f"balance:{account}")
        if hit is not None:
            return int(hit)
        value = balance(account)
        cache.set(f"balance:{account}", str(value))
        return value
    finally:
        cache.close()
