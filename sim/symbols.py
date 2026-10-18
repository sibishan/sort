"""The shared Unicode alphabet and input normalization rules."""

from typing import Iterable, Iterator
import unicodedata

START_STATE = "⎆"
ACCEPT_STATE = "✔"
ERROR_STATE = "❗"
DEFAULT_BLANK = "·"
RESERVED_STATES = {START_STATE, ACCEPT_STATE, ERROR_STATE}


class MachineError(ValueError):
    """An invalid machine definition, input tape, or run configuration."""


def is_tape_symbol(value: str) -> bool:
    return len(value) == 1 and unicodedata.category(value)[0] in "LNPS"


def is_state_name(value: str) -> bool:
    return bool(value) and value not in RESERVED_STATES and all(map(is_tape_symbol, value))


def iter_input_symbols(input_tape: Iterable[str]) -> Iterator[str]:
    """Normalize text before splitting; normalize explicit cells independently."""
    if isinstance(input_tape, str):
        input_tape = unicodedata.normalize("NFC", input_tape)
    try:
        iterator = iter(input_tape)
    except TypeError as error:
        raise MachineError("Input tape must be a string or an iterable of symbols.") from error
    for index, token in enumerate(iterator):
        if not isinstance(token, str):
            raise MachineError(f"Input cell {index}: expected one Unicode tape symbol.")
        symbol = unicodedata.normalize("NFC", token)
        if symbol == DEFAULT_BLANK:
            raise MachineError(f"Input cell {index}: the blank symbol · is not allowed in input.")
        if not is_tape_symbol(symbol):
            raise MachineError(
                f"Input cell {index}: {symbol!r} must be one Unicode letter, number, punctuation mark, or symbol."
            )
        yield symbol


def iter_normalized_characters(chunks: Iterable[str]) -> Iterator[str]:
    """Normalize streamed text, retaining the last canonical segment between chunks.

    The retained starter can still compose with a following chunk, including
    combining accents and Hangul Jamo whose combining class is zero. Ordinary
    text needs just one retained character; combining runs stay together.
    Explicit token streams should use iter_input_symbols instead.
    """
    pending = ""
    for chunk in chunks:
        if not isinstance(chunk, str):
            raise MachineError("Text chunks must be strings.")
        if not chunk:
            continue
        normalized = unicodedata.normalize("NFC", pending + chunk)
        boundary = len(normalized) - 1
        while boundary > 0 and unicodedata.combining(normalized[boundary]):
            boundary -= 1
        yield from normalized[:boundary]
        pending = normalized[boundary:]
    yield from pending
