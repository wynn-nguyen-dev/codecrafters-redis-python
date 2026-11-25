import time

from app.errors import WrongTypeError


def normalize_index_range(start: int, stop: int, length: int) -> tuple[int, int] | None:
    if start < 0:
        start = max(start + length, 0)

    if stop < 0:
        stop += length

    stop = min(stop, length - 1)

    if start >= stop or start >= length:
        return None

    return start, stop


class Store:
    def __init__(self) -> None:
        self._data: dict[bytes, tuple[bytes | list[bytes], float | None]] = {}

    @staticmethod
    def _is_expired(expiry: float | None) -> bool:
        return expiry is not None and time.monotonic() >= expiry

    def _get_entry(self, key: bytes) -> tuple[bytes | list[bytes], float | None] | None:
        entry = self._data.get(key)

        if entry is None:
            return None

        if self._is_expired(entry[1]):
            del self._data[key]
            return None

        return entry

    def set(
        self, key: bytes, value: bytes | list[bytes], expiry: float | None = None
    ) -> None:
        self._data[key] = (value, expiry)

    def get(self, key: bytes) -> bytes | None:
        entry = self._get_entry(key)

        if entry is None:
            return None

        value = entry[0]

        if not isinstance(value, bytes):
            raise WrongTypeError()

        return value

    def rpush(self, key: bytes, items: list[bytes]) -> int:
        entry = self._get_entry(key)

        if entry is None:
            self._data[key] = (list(items), None)
            return len(items)

        value, _ = entry

        if not isinstance(value, list):
            raise WrongTypeError()

        value.extend(items)
        return len(value)

    def lpush(self, key: bytes, items: list[bytes]) -> int:
        entry = self._get_entry(key)

        if entry is None:
            self._data[key] = (list(items), None)
            return len(items)

        value, _ = entry

        if not isinstance(value, list):
            raise WrongTypeError()

        value[:0] = items[::-1]
        return len(value)

    def lrange(self, key: bytes, raw_start: int, raw_stop: int) -> list[bytes]:
        entry = self._get_entry(key)

        if entry is None:
            return []

        value, _ = entry
        if not isinstance(value, list):
            raise WrongTypeError()

        range_ = normalize_index_range(raw_start, raw_stop, len(value))

        if range_ is None:
            return []

        s, e = range_

        return value[s : e + 1]

    def llen(self, key: bytes) -> int:
        entry = self._get_entry(key)

        if entry is None:
            return 0

        value, _ = entry
        if not isinstance(value, list):
            raise WrongTypeError()

        return len(value)

    def lpop(self, key: bytes) -> bytes | None:
        entry = self._get_entry(key)

        if entry is None:
            return None

        value, _ = entry
        if not isinstance(value, list):
            raise WrongTypeError()

        return value.pop(0)

    def delete(self, key: bytes) -> bool:
        entry = self._get_entry(key)

        if entry is None:
            return False

        del self._data[key]
        return True
