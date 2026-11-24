import time


class Store:
    def __init__(self) -> None:
        self._data: dict[bytes, tuple[bytes, float | None]] = {}

    @staticmethod
    def _is_expired(expiry: float | None) -> bool:
        return expiry is not None and time.monotonic() >= expiry

    def _get_entry(self, key: bytes) -> tuple[bytes, float | None] | None:
        entry = self._data.get(key)

        if entry is None:
            return None

        if self._is_expired(entry[1]):
            del self._data[key]
            return None

        return entry

    def set(self, key: bytes, val: bytes, expiry: float | None = None) -> None:
        self._data[key] = (val, expiry)

    def get(self, key: bytes) -> bytes | None:
        entry = self._get_entry(key)
        return None if entry is None else entry[0]

    def delete(self, key: bytes) -> bool:
        entry = self._get_entry(key)

        if entry is None:
            return False

        del self._data[key]
        return True
