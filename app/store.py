import asyncio
import time
from collections import defaultdict, deque

from app.errors import MuseBePositiveIntegerError, WrongTypeError


def normalize_index_range(start: int, stop: int, length: int) -> tuple[int, int] | None:
    """Convert Redis-style indexes into a concrete inclusive range.

    Negative indexes count from the end (-1 is the last element) and `stop`
    is inclusive. Out-of-range values are clamped.

    Returns:
        (start, stop) as valid inclusive indexes, or None if the range is empty.
    """
    if start < 0:
        start = max(start + length, 0)

    if stop < 0:
        stop += length

    stop = min(stop, length - 1)

    if start > stop or start >= length:
        return None

    return start, stop


class Store:
    """In-memory key/value store with lazy expiry and list support.

    Values are either `bytes` (string) or `list[bytes]` (list). Expiry is an
    absolute `time.monotonic()` deadline. Expired keys are removed lazily on
    access. Methods that read a key with the wrong type raise `WrongTypeError`.
    """

    def __init__(self) -> None:
        self._data: dict[bytes, tuple[bytes | list[bytes], float | None]] = {}
        self._waiters: defaultdict[bytes, deque[asyncio.Future[None]]] = defaultdict(
            deque
        )

    @staticmethod
    def _is_expired(expiry: float | None) -> bool:
        return expiry is not None and time.monotonic() >= expiry

    def _get_entry(self, key: bytes) -> tuple[bytes | list[bytes], float | None] | None:
        """Return the live entry for `key`, or None.

        An expired entry is deleted here (lazy expiry) and reported as missing.
        All reads should go through this method so expiry is handled in one place.
        """
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
            self._notify(key)
            return len(items)

        value, _ = entry

        if not isinstance(value, list):
            raise WrongTypeError()

        value.extend(items)
        self._notify(key)
        return len(value)

    def lpush(self, key: bytes, items: list[bytes]) -> int:
        entry = self._get_entry(key)

        if entry is None:
            self._data[key] = (list(items), None)
            self._notify(key)
            return len(items)

        value, _ = entry

        if not isinstance(value, list):
            raise WrongTypeError()

        value[:0] = items[::-1]
        self._notify(key)
        return len(value)

    def lrange(self, key: bytes, raw_start: int, raw_stop: int) -> list[bytes]:
        """Return the elements in the inclusive range [start, stop].

        Returns an empty list for a missing key or an empty range.
        Raises:
            WrongTypeError: if the key holds a string.
        """
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

    def lpop(self, key: bytes, count: int | None = None) -> bytes | list[bytes] | None:
        """Remove and return elements from the head of the list at `key`.

        The return shape depends on `count`:
            count is None -> a single element, or None if the key is missing
            count given   -> a list of up to `count` elements (possibly empty)

        The key is deleted when the list becomes empty, since Redis never
        keeps empty lists.

        Raises:
            WrongTypeError: if the key holds a string.
            MuseBePositiveIntegerError: if `count` is negative.
        """

        entry = self._get_entry(key)

        if entry is None:
            return None

        value, _ = entry
        if not isinstance(value, list):
            raise WrongTypeError()

        if count is not None and count < 0:
            raise MuseBePositiveIntegerError()

        n = 1 if count is None else count
        items = self._pop_head(key, value, n)

        if count is None:
            return items[0] if items else None

        return items

    def delete(self, key: bytes) -> bool:
        entry = self._get_entry(key)

        if entry is None:
            return False

        del self._data[key]
        return True

    def _notify(self, key: bytes) -> None:
        """Wake exactly one task blocked on `key`, skipping cancelled waiters.

        Called after every push. It only signals; the woken task performs the
        pop itself, so push operations stay unaware of blocking commands.
        """

        entry = self._waiters.get(key)

        if not entry:
            return

        while entry:
            fut = entry.popleft()

            if fut.done():
                continue

            fut.set_result(None)
            break

        if not entry:
            self._waiters.pop(key, None)

    def _pop_head(self, key: bytes, value: list[bytes], n: int) -> list[bytes]:
        """Remove up to `n` elements from the head of `value`.

        Deletes the key if the list becomes empty (Redis never keeps empty lists).
        """
        items = value[:n]
        del value[:n]

        if not value:
            del self._data[key]

        return items

    async def blpop(self, key: bytes, timeout: float | None) -> bytes | None:
        """Pop the head of the list at `key`, waiting for a push if empty.

        Waiters are served in FIFO order. After being woken, the task retries
        the pop, because another client may have taken the element first.

        Args:
            timeout: seconds to wait, or None to wait forever.
        Returns:
            The popped element, or None if the timeout elapsed.
        """

        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + timeout

        while True:
            entry = self._get_entry(key)

            if entry is not None:
                value, _ = entry

                if not isinstance(value, list):
                    raise WrongTypeError()

                if value:
                    item = self._pop_head(key, value, 1)[0]

                    if key in self._data:
                        self._notify(key)

                    return item

            remaining = None if deadline is None else deadline - loop.time()

            if remaining is not None and remaining <= 0:
                return None

            fut = loop.create_future()
            waiters = self._waiters[key]
            waiters.append(fut)

            try:
                await asyncio.wait_for(fut, remaining)
            except TimeoutError:
                return None
            except asyncio.CancelledError:
                if fut.done() and not fut.cancelled():
                    self._notify(key)
                raise
            finally:
                try:
                    waiters.remove(fut)
                except ValueError:
                    pass

                if not waiters and self._waiters[key] is waiters:
                    del self._waiters[key]
