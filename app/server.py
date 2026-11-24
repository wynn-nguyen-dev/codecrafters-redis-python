import asyncio

from app import commands, resp
from app.store import Store


def make_handle_client(store: Store):
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                args = await resp.read_command(reader)

                if not args:
                    continue

                handler = commands.get_handler(args[0])

                if handler is None:
                    response = resp.error(b"unknown command")
                else:
                    try:
                        response = handler(store, args)
                    except IndexError, ValueError:
                        response = resp.error(
                            b"wrong number of arguments or invalid value"
                        )

                writer.write(response)
                await writer.drain()
        except asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    return handle_client


async def run_server(host="127.0.0.1", port=6379):
    store = Store()
    server = await asyncio.start_server(make_handle_client(store), host, port)

    async with server:
        await server.serve_forever()
