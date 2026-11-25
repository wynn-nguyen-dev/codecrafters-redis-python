import time
from collections.abc import Callable

from app import resp
from app.errors import InvalidExpireError, NotIntegerError, SyntaxErr, WrongArgsError
from app.store import Store

Handler = Callable[[Store, list[bytes]], resp.Value]
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
def cmd_ping(store: Store, args: list[bytes]) -> resp.Value:
    return resp.PONG


@command(b"ECHO")
def cmd_echo(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) != 2:
        raise WrongArgsError(b"ECHO")
    return args[1]


EXPIRE_UNITS = {b"PX": 0.001, b"EX": 1.0}


@command(b"SET")
def cmd_set(store: Store, args: list[bytes]) -> resp.Value:
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

    return resp.OK


@command(b"GET")
def cmd_get(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) != 2:
        raise WrongArgsError(b"GET")

    return store.get(args[1])


@command(b"RPUSH")
def cmd_rpush(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) < 3:
        raise WrongArgsError(b"RPUSH")

    return store.rpush(args[1], args[2:])


@command(b"LPUSH")
def cmd_lpush(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) < 3:
        raise WrongArgsError(b"LPUSH")

    return store.lpush(args[1], args[2:])


@command(b"LLEN")
def cmd_llen(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) != 2:
        raise WrongArgsError(b"LLEN")

    return store.llen(args[1])

@command(b"LPOP")
def cmd_lpop(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) != 2:
        raise WrongArgsError(b"LPOP")

    return store.lpop(args[1])


@command(b"LRANGE")
def cmd_lrange(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) != 4:
        raise WrongArgsError(b"LRANGE")

    try:
        start, stop = int(args[2]), int(args[3])
    except ValueError:
        raise NotIntegerError() from None

    return store.lrange(args[1], start, stop)
