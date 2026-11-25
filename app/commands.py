import time
from collections.abc import Callable

from app import resp
from app.errors import InvalidExpireError, NotIntegerError, SyntaxErr, WrongArgsError
from app.store import Store

Handler = Callable[[Store, list[bytes]], bytes]
COMMANDS: dict[bytes, Handler] = {}


def get_handler(cmd: bytes):
    return COMMANDS.get(cmd.upper())


def command(cmd: bytes):
    """Decorator to register handler to COMMANDS"""

    def decorator(fn: Handler) -> Handler:
        COMMANDS[cmd.upper()] = fn
        return fn

    return decorator


@command(b"PING")
def cmd_ping(store: Store, args: list[bytes]) -> bytes:
    return resp.simple(b"PONG")


@command(b"ECHO")
def cmd_echo(store: Store, args: list[bytes]) -> bytes:
    if len(args) != 2:
        raise WrongArgsError(b"ECHO")
    return resp.bulk(args[1])


EXPIRE_UNITS = {b"PX": 0.001, b"EX": 1.0}


@command(b"SET")
def cmd_set(store: Store, args: list[bytes]) -> bytes:
    if len(args) < 3:
        raise WrongArgsError(b"SET")

    _, key, value, *opts = args

    expiry = None
    it = iter(opts)

    for raw_opt in it:
        opt = raw_opt.upper()

        if opt not in EXPIRE_UNITS:
            raise SyntaxErr()

        if expiry is not None:  # ! PX 100 EX 5
            raise SyntaxErr()

        raw = next(it, None)

        if raw is None:
            raise SyntaxErr()

        try:
            amount = int(raw)
        except ValueError:
            raise NotIntegerError()

        if amount <= 0:
            raise InvalidExpireError(b"SET")

        expiry = time.monotonic() + amount * EXPIRE_UNITS[opt]

    store.set(key, value, expiry)

    return resp.simple(b"OK")


@command(b"GET")
def cmd_get(store: Store, args: list[bytes]) -> bytes:
    if len(args) != 2:
        raise WrongArgsError(b"GET")

    return resp.bulk(store.get(args[1]))


@command(b"RPUSH")
def cmd_rpush(store: Store, args: list[bytes]) -> bytes:
    if len(args) < 3:
        raise WrongArgsError(b"RPUSH")

    return resp.integer(store.rpush(args[1], args[2:]))
