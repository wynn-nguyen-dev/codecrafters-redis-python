from typing import Literal


class RedisError(Exception):
    """Base class for errors that are reported to the client.

    Subclasses set `kind` (the RESP error prefix, e.g. ERR, WRONGTYPE).
    The server catches this type and converts it into a RESP error reply;
    any other exception is treated as a server bug.
    """
    kind: Literal[b"ERR", b"WRONGTYPE"] | bytes = b"ERR"

    def __init__(self, message: bytes) -> None:
        super().__init__(message)
        self.message = message


class UnknownCommandError(RedisError):
    def __init__(self, cmd: bytes) -> None:
        super().__init__(b"unknown command '%s'" % cmd)


class WrongTypeError(RedisError):
    kind = b"WRONGTYPE"

    def __init__(
        self,
        message: bytes = b"Operation against a key holding the wrong kind of value",
    ) -> None:
        super().__init__(message)


class SyntaxErr(RedisError):
    def __init__(self) -> None:
        super().__init__(b"syntax error")


class NotIntegerError(RedisError):
    def __init__(self) -> None:
        super().__init__(b"value is not an integer or out of range")


class WrongArgsError(RedisError):
    def __init__(self, cmd: bytes) -> None:
        super().__init__(b"wrong number of arguments for '%s' command" % cmd.lower())


class InvalidExpireError(RedisError):
    def __init__(self, cmd: bytes) -> None:
        super().__init__(b"invalid expire time in '%s' command" % cmd.lower())


class MuseBePositiveIntegerError(RedisError):
    def __init__(self) -> None:
        super().__init__(b"value is out of range, must be positive")


class InvalidTimeoutError(RedisError):
    def __init__(
        self, message: bytes = b"timeout is not a float or out of range"
    ) -> None:
        super().__init__(message)
