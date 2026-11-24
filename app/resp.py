import asyncio

CRLF = b"\r\n"


def simple(s: bytes) -> bytes:
    return b"+%s\r\n" % s


def bulk(s: bytes | None) -> bytes:
    if s is None:
        return b"$-1\r\n"
    return b"$%d\r\n%s\r\n" % (len(s), s)


def error(msg: bytes) -> bytes:
    return b"-ERR %s\r\n" % msg


def integer(n: int) -> bytes:
    return b":%d\r\n" % n


def array(items: list[bytes] | None) -> bytes:
    if items is None:
        return b"*-1\r\n"
    return b"*%d\r\n" % len(items) + b"".join(items)


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
