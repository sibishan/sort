"""Compact paged tape storage, with optional disk backing."""

from array import array
from itertools import islice
import mmap
import tempfile
from typing import Iterable, Iterator, Optional

PAGE_CELLS = 65_536
CELL_BYTES = array("I").itemsize
if CELL_BYTES != 4:
    raise RuntimeError("Tape storage requires a four-byte unsigned integer type.")


class Tape:
    """Allocate pages for nonblank data and retain zero-filled gaps implicitly."""

    def __init__(self) -> None:
        self.page_indices: set[int] = set()
        self.closed = False

    def get_page(self, index: int):
        raise NotImplementedError

    def ensure_page(self, index: int):
        raise NotImplementedError

    def load(self, symbols: Iterable[int]) -> int:
        iterator = iter(symbols)
        length = 0
        index = 0
        while True:
            chunk = array("I", islice(iterator, PAGE_CELLS))
            if not chunk:
                return length
            if any(chunk):
                page = self.ensure_page(index)
                page[:len(chunk)] = chunk
            length += len(chunk)
            index += 1

    def bounds(self, max_position: int) -> tuple[int, int]:
        """Find nonblank bounds without materializing or scanning blank gaps."""
        indices = sorted(self.page_indices)
        start = None
        for index in indices:
            page = self.get_page(index)
            stop = min(PAGE_CELLS, max_position - index * PAGE_CELLS + 1)
            for offset in range(stop):
                if page[offset]:
                    start = index * PAGE_CELLS + offset
                    break
            if start is not None:
                break
        if start is None:
            return 0, -1
        for index in reversed(indices):
            page = self.get_page(index)
            stop = min(PAGE_CELLS - 1, max_position - index * PAGE_CELLS)
            for offset in range(stop, -1, -1):
                if page[offset]:
                    return start, index * PAGE_CELLS + offset
        raise RuntimeError("Tape bounds are inconsistent.")

    def iter_symbols(self, start: int, end: int, symbols: tuple[str, ...]) -> Iterator[str]:
        if self.closed:
            raise ValueError("The result tape has been closed.")
        position = start
        while position <= end:
            index, offset = divmod(position, PAGE_CELLS)
            page = self.get_page(index)
            stop = min(PAGE_CELLS, end - index * PAGE_CELLS + 1)
            if page is None:
                for _ in range(offset, stop):
                    yield symbols[0]
            else:
                for cell in range(offset, stop):
                    yield symbols[page[cell]]
            position = (index + 1) * PAGE_CELLS

    def close(self) -> None:
        self.closed = True


class MemoryTape(Tape):
    def __init__(self) -> None:
        super().__init__()
        self.pages: dict[int, array] = {}

    def get_page(self, index: int) -> Optional[array]:
        return self.pages.get(index)

    def ensure_page(self, index: int) -> array:
        page = self.pages.get(index)
        if page is None:
            page = array("I", [0]) * PAGE_CELLS
            self.pages[index] = page
            self.page_indices.add(index)
        return page

    def close(self) -> None:
        self.pages.clear()
        self.page_indices.clear()
        super().close()


class _DiskPage:
    """Refer through the owner so growing the mapping keeps page handles valid."""

    __slots__ = ("tape", "offset")

    def __init__(self, tape: "DiskTape", index: int) -> None:
        self.tape = tape
        self.offset = index * PAGE_CELLS

    def __getitem__(self, index: int) -> int:
        return self.tape.view[self.offset + index]

    def __setitem__(self, index, value) -> None:
        if isinstance(index, slice):
            start, stop, step = index.indices(PAGE_CELLS)
            self.tape.view[self.offset + start:self.offset + stop:step] = value
        else:
            self.tape.view[self.offset + index] = value


class DiskTape(Tape):
    """Use a temporary memory-mapped file; the OS pages data to and from disk."""

    def __init__(self, directory: Optional[str] = None) -> None:
        super().__init__()
        self.file = tempfile.TemporaryFile(dir=directory)
        self.mapping = None
        self.view = None
        self.capacity = 0

    def get_page(self, index: int) -> Optional[_DiskPage]:
        if index not in self.page_indices:
            return None
        return _DiskPage(self, index)

    def ensure_page(self, index: int) -> _DiskPage:
        needed = (index + 1) * PAGE_CELLS
        if needed > self.capacity:
            # Grow in bounded increments once mappings become large.
            capacity = max(needed, self.capacity + min(max(self.capacity, PAGE_CELLS), 16_777_216))
            if self.view is not None:
                self.view.release()
                self.view = None
            if self.mapping is not None:
                self.mapping.close()
                self.mapping = None
            self.file.truncate(capacity * CELL_BYTES)
            self.mapping = mmap.mmap(self.file.fileno(), capacity * CELL_BYTES)
            self.view = memoryview(self.mapping).cast("I")
            self.capacity = capacity
        self.page_indices.add(index)
        return _DiskPage(self, index)

    def close(self) -> None:
        if self.view is not None:
            self.view.release()
            self.view = None
        if self.mapping is not None:
            self.mapping.close()
            self.mapping = None
        self.file.close()
        self.page_indices.clear()
        super().close()
