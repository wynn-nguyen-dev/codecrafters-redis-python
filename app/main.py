import asyncio

store: dict[bytes, bytes] = {}

CLRF_BYTES = b"\r\n"

ARRAY_BYTES_TYPE = b"*"

BULK_BYTES_TYPE = b"$"


def simple_string(b: bytes):
    return b"+" + b + CLRF_BYTES


def bulk_string(b: bytes | None):
    if b is None:
        return BULK_BYTES_TYPE + str(-1).encode() + CLRF_BYTES

    return BULK_BYTES_TYPE + str(len(b)).encode() + CLRF_BYTES + b + CLRF_BYTES


async def read_command(reader: asyncio.StreamReader) -> list[bytes]:
    line = await reader.readuntil(CLRF_BYTES)

    args = []

    if line[0] != ord(ARRAY_BYTES_TYPE):
        return args

    n = int(line[1:-2])

    for _ in range(n):
        header = await reader.readuntil(CLRF_BYTES)
        length = int(header[1:-2])
        data = await reader.readexactly(length + 2)
        args.append(data[:-2])

    return args


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            args = await read_command(reader)

            if len(args) < 1:
                continue

            cmd = args[0].upper()

            if cmd == b"PING":
                writer.write(b"+PONG" + CLRF_BYTES)
            elif cmd == b"ECHO":
                msg = args[1]

                writer.write(bulk_string(msg))
            elif cmd == b"SET":
                key, val = args[1], args[2]
                store[key] = val

                writer.write(simple_string(b"OK"))
            elif cmd == b"GET":
                key = args[1]

                val = store.get(key)

                writer.write(bulk_string(val))
                

            await writer.drain()
    except asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def main(host="127.0.0.1", port=6379):
    server = await asyncio.start_server(handle_client, host, port)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
