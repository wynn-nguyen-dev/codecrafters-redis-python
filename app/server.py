import asyncio
import logging

from app import commands, resp
from app.errors import RedisError
from app.store import Store

logger = logging.getLogger(__name__)


def make_handle_client(store: Store):
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                args = await resp.read_command(reader)

                if not args:
                    continue

                handler = commands.get_handler(args[0])

                if handler is None:
                    response = resp.Error(b"unknown command '%s'" % args[0])
                else:
                    try:
                        response = handler(store, args)
                    except RedisError as e:
                        response = resp.Error(e.message, e.kind)
                    except Exception:
                        logger.exception("handler crashed: %r", args)
                        response = resp.Error(
                            b"wrong number of arguments or invalid value"
                        )

                writer.write(resp.encode(response))
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
