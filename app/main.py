import asyncio


async def read_command(reader: asyncio.StreamReader) -> list[bytes]:
    line = await reader.readuntil(b"\r\n")

    args = []

    if line[0] != ord("*"):
        return args

    n = int(line[1:-2])

    for _ in range(n):
        header = await reader.readuntil(b"\r\n")
        print("header:", header)
        length = int(header[1:-2])
        arg = header[length:-2]
        print("arg:",arg)
        args.append(arg)

    print(args)
    return args


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        # while await reader.read(1024):
        #     writer.write(b"+PONG\r\n")
        #     await writer.drain()
        args = await read_command(reader)

        if len(args) < 1:
            return
        
        cmd = args[0].upper()

        if cmd == b"PING":
            writer.write(b"+PONG\r\n")
        elif cmd == b"ECHO":
            writer.write(args[1])

        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def main(host="127.0.0.1", port=6379):
    server = await asyncio.start_server(handle_client, host, port)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
