import asyncio
from collections.abc import Sequence
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


@dataclass(frozen=True, slots=True)
class NullArray:
    """Marker for the RESP null array (`*-1\\r\\n`).

    Distinct from `None` (null bulk string), because some commands
    (e.g. BLPOP on timeout) must reply with a null *array*.
    """


OK = Simple(b"OK")
PONG = Simple(b"PONG")
NULL_ARRAY = NullArray()

type Value = None | bytes | int | Simple | Error | NullArray | Sequence[Value]
"""A Python value that `encode` can serialize to RESP.

Mapping:
    None      -> null bulk string ($-1)
    bytes     -> bulk string
    int       -> integer
    Simple    -> simple string
    Error     -> simple error
    NullArray -> null array (*-1)
    Sequence  -> array (elements encoded recursively)
"""


def encode(v: Value) -> bytes:
    """Serialize a Python value into RESP bytes.

    The `bool` case must precede `int` because `bool` subclasses `int`.
    Raises:
        TypeError: if `v` is not a supported type.
    """
    match v:
        case None:
            return b"$-1\r\n"
        case Simple(value):
            return b"+%s\r\n" % value
        case NullArray():
            return b"*-1\r\n"
        case Error(message, kind):
            return b"-%s %s\r\n" % (kind, message)
        case bool():
            raise TypeError("bool is not a RESP value")
        case int():
            return b":%d\r\n" % v
        case bytes():
            return b"$%d\r\n%s\r\n" % (len(v), v)
        case list() | tuple():
            return b"*%d\r\n" % len(v) + b"".join(encode(x) for x in v)
        case _:
            raise TypeError(f"cannot encode {type(v)}")


async def read_command(reader: asyncio.StreamReader) -> list[bytes]:
    """Read one RESP array command from the stream and return its arguments.

    Returns an empty list if the input does not start with an array marker.
    Raises:
        asyncio.IncompleteReadError: if the client disconnects mid-command.
    """
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
