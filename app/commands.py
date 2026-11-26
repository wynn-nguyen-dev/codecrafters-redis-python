import inspect
import time
from collections.abc import Awaitable, Callable

from app import resp
from app.errors import (
    InvalidExpireError,
    InvalidTimeoutError,
    NotIntegerError,
    SyntaxErr,
    UnknownCommandError,
    WrongArgsError,
)
from app.store import Store

type HandlerReturn = resp.Value | Awaitable[resp.Value]
type Handler = Callable[[Store, list[bytes]], HandlerReturn]
"""A command handler. May be sync (returns a Value) or async (returns an
awaitable Value). `run_handler` hides the difference from the server."""

COMMANDS: dict[bytes, Handler] = {}


def get_handler(cmd: bytes):
    return COMMANDS.get(cmd.upper())


def command(cmd: bytes):
    """Register a handler under `cmd` (case-insensitive).

    Works for both sync and async handlers. Returns the original function
    unchanged, so handlers can still be called directly in tests.
    """

    def decorator(fn: Handler) -> Handler:
        COMMANDS[cmd.upper()] = fn
        return fn

    return decorator


async def run_handler(store: Store, args: list[bytes]) -> resp.Value:
    """Look up and execute the handler for `args[0]`, awaiting it if needed.

    Sync handlers never yield to the event loop, so each runs atomically
    relative to other clients. Only async handlers (e.g. BLPOP) may suspend.

    Raises:
        UnknownCommandError: if no handler is registered for the command.
        RedisError: propagated from the handler.
    """
    handler = COMMANDS.get(args[0].upper())

    if handler is None:
        raise UnknownCommandError(args[0])

    result = handler(store, args)

    if inspect.isawaitable(result):
        return await result

    return result


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
    if len(args) not in (2, 3):
        raise WrongArgsError(b"LPOP")

    if len(args) == 2:
        return store.lpop(args[1])

    try:
        count = int(args[2])
    except ValueError:
        raise NotIntegerError() from None

    return store.lpop(args[1], count)


@command(b"LRANGE")
def cmd_lrange(store: Store, args: list[bytes]) -> resp.Value:
    if len(args) != 4:
        raise WrongArgsError(b"LRANGE")

    try:
        start, stop = int(args[2]), int(args[3])
    except ValueError:
        raise NotIntegerError() from None

    return store.lrange(args[1], start, stop)


def parse_timeout(raw: bytes) -> float | None:
    """Parse a blocking-command timeout given in seconds (may be fractional).

    Returns:
        None for 0 (block forever), otherwise the timeout in seconds.
    Raises:
        InvalidTimeoutError: if not a number, or negative.
    """

    try:
        timeout = float(raw)
    except ValueError:
        raise InvalidTimeoutError()

    if timeout < 0:
        raise InvalidTimeoutError(b"timeout is negative")

    if timeout == 0:
        return None

    return timeout


@command(b"BLPOP")
async def cmd_blpop(store: Store, args: list[bytes]) -> resp.Value:
    """BLPOP key timeout

    Pop the first element of the list at `key`, waiting up to `timeout`
    seconds if it is empty (0 = forever).

    Returns:
        [key, value] on success, or a null array on timeout.
    """
    if len(args) != 3:
        raise WrongArgsError(b"BLPOP")

    key = args[1]
    timeout = parse_timeout(args[2])

    value = await store.blpop(key, timeout)

    if value is None:
        return resp.NULL_ARRAY

    return [key, value]

