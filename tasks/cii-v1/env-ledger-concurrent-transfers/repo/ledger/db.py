"""Connections to the run's services, resolved from .vb_services.json."""

import json
import socket
from pathlib import Path

import psycopg2


def _services() -> dict:
    for base in (Path.cwd(), *Path.cwd().parents):
        manifest = base / ".vb_services.json"
        if manifest.exists():
            return json.loads(manifest.read_text())["services"]
    raise RuntimeError(".vb_services.json not found; is the environment up?")


def pg_connect():
    port = int(_services()["postgres"]["5432"])
    return psycopg2.connect(
        host="127.0.0.1", port=port, user="vb", password="vb", dbname="ledger"
    )


class Redis:
    """A minimal RESP client; enough for GET/SET/DEL against the cache."""

    def __init__(self) -> None:
        port = int(_services()["redis"]["6379"])
        self._sock = socket.create_connection(("127.0.0.1", port), timeout=5)

    def _cmd(self, *parts: str) -> bytes:
        payload = f"*{len(parts)}\r\n" + "".join(f"${len(p)}\r\n{p}\r\n" for p in parts)
        self._sock.sendall(payload.encode())
        return self._sock.recv(65536)

    def get(self, key: str) -> str | None:
        reply = self._cmd("GET", key)
        if reply.startswith(b"$-1"):
            return None
        return reply.split(b"\r\n", 2)[1].decode()

    def set(self, key: str, value: str) -> None:
        self._cmd("SET", key, value)

    def delete(self, key: str) -> None:
        self._cmd("DEL", key)

    def close(self) -> None:
        self._sock.close()
