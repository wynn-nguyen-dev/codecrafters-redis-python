import asyncio
from dataclasses import dataclass
from typing import Literal

CRLF = b"\r\n"


@dataclass(frozen=True, slots=True)
class Simple:
    value: bytes


@dataclass(frozen=True, slots=True)
class Error:
    message: bytes
    kind: Literal[b"ERR", b"WRONGTYPE"] | bytes = b"ERR"


OK = Simple(b"OK")
PONG = Simple(b"PONG")

Value = None | bytes | int | Simple | Error | list["Value"]


def encode(v: Value) -> bytes:
    match v:
        case None:
            return b"$-1\r\n"
        case Simple(value):
            return b"+%s\r\n" % value
        case Error(message, kind):
            return b"-%s %s\r\n" % (kind, message)
        case bool():
            raise TypeError("bool is not a RESP value")
        case int():
            return b":%d\r\n" % v
        case bytes():
            return b"$%d\r\n%s\r\n" % (len(v), v)
        case list():
            return b"*%d\r\n" % len(v) + b"".join(encode(x) for x in v)
        case _:
            raise TypeError(f"cannot encode {type(v)}")


async def read_command(reader: asyncio.StreamReader) -> list[bytes]:
    line = await reader.readuntil(CRLF)

    if line[:1] != b"*":
        return []

    n = int(line[1:-2])
    args = []

    for _ in range(n):
        header = await reader.readuntil(CRLF)
        length = int(header[1:-2])
        data = await reader.readexactly(length + 2)
        args.append(data[:-2])

    return args
