# Ledger loses money under load; retried events double-apply; cache serves wrong balances

Production incident, reproduced against this service with its real
Postgres and Redis (this run's stack is up — ports are in
`.vb_services.json`; see `ledger/db.py` for how connections resolve).

Three symptom reports from the last on-call rotation:

1. **The books don't balance.** Under concurrent transfer traffic between
   the same accounts, the sum of all balances drifts from the invariant —
   money is created or destroyed. With bidirectional traffic (A→B and B→A
   at once) we additionally see transactions aborting with database
   errors.

2. **Event retries double-apply.** Our upstream queue redelivers events;
   `apply_event` is supposed to be idempotent per event id. When retries
   land concurrently, an event's delta is sometimes applied twice, and
   sometimes a retry crashes instead of returning `False`.

3. **The balance cache lies.** After a transfer is *rejected* for
   insufficient funds, `cached_balance` on the source account returns a
   number that was never the balance. After a *successful* transfer,
   `cached_balance` on the destination keeps returning the old value.

Fix the service so its invariants hold under concurrent access from
multiple processes: money is conserved and transfers never error under
contention (including bidirectional traffic), events apply exactly once
with retries returning `False` rather than raising, and `cached_balance`
never returns a value the database has not committed — while still being
served from Redis on the hot path.

The public API (`transfer`, `balance`, `apply_event`, `cached_balance`,
`InsufficientFunds`) and all sequential behavior must not change:
overdrafts still reject and leave state untouched, non-positive amounts
still raise `ValueError`, unknown accounts still raise `KeyError`, and
reads must still be served from the cache when it is warm.
