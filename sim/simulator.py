"""Parse a machine once and execute it without animation or step history."""

if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from runner.cli import main

    raise SystemExit(main())

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional
import unicodedata

from .tape import DiskTape, MemoryTape, PAGE_CELLS, Tape
from .symbols import (
    ACCEPT_STATE, DEFAULT_BLANK, ERROR_STATE, START_STATE, MachineError,
    is_state_name, is_tape_symbol, iter_input_symbols,
)

DEFAULT_MAX_STEPS = 1_000_000
MOVES = {"←": -1, "→": 1, "⏹": 0}

# Integer state and symbol IDs keep strings out of the execution loop.
Action = tuple[int, int, int]  # write symbol, next state, movement
AMBIGUOUS_ACTION: Action = (-1, -1, 0)


@dataclass(frozen=True, slots=True)
class RunResult:
    status: str
    final_state: str
    steps: int
    head_position: int
    tape_start: int
    blank_symbol: str
    tape_end: int
    input_length: int
    _tape: Tape = field(repr=False)
    _symbols: tuple[str, ...] = field(repr=False)
    message: str = ""

    @property
    def tape_length(self) -> int:
        return max(0, self.tape_end - self.tape_start + 1)

    @property
    def tape_tokens(self) -> list[str]:
        """Convenience for small tapes; use iter_tokens for large results."""
        return list(self.iter_tokens())

    def iter_tokens(self) -> Iterator[str]:
        return self._tape.iter_symbols(self.tape_start, self.tape_end, self._symbols)

    def iter_text_chunks(self, chunk_size: int = 65_536) -> Iterator[str]:
        """Concatenate symbols in bounded chunks, including long symbols."""
        if chunk_size < 1:
            raise ValueError("Chunk size must be positive.")
        parts = []
        length = 0
        for symbol in self.iter_tokens():
            offset = 0
            while offset < len(symbol):
                take = min(chunk_size - length, len(symbol) - offset)
                parts.append(symbol[offset:offset + take])
                offset += take
                length += take
                if length == chunk_size:
                    yield "".join(parts)
                    parts = []
                    length = 0
        if parts:
            yield "".join(parts)

    def close(self) -> None:
        self._tape.close()

    def __enter__(self) -> "RunResult":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def to_dict(self, *, include_tape: bool = True) -> dict:
        """Materialize small results, or return only metadata for large tapes."""
        result = {
            "status": self.status,
            "finalState": self.final_state,
            "steps": self.steps,
            "finalHeadPosition": self.head_position,
            "finalTapeStart": self.tape_start,
            "finalTapeLength": self.tape_length,
            "inputLength": self.input_length,
            "blankSymbol": self.blank_symbol,
        }
        if self.message:
            result["message"] = self.message
        if include_tape:
            tokens = self.tape_tokens
            result["finalTape"] = "".join(tokens)
            result["finalTapeTokens"] = tokens
        return result


@dataclass(frozen=True, slots=True)
class Machine:
    states: tuple[str, ...]
    symbols: tuple[str, ...]
    symbol_ids: dict[str, int]
    table: tuple[tuple[Optional[Action], ...], ...]
    terminal_statuses: tuple[Optional[str], ...]
    ambiguities: dict[tuple[int, int], tuple[int, ...]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_tsv(cls, text: str, *, blank_symbol: str = DEFAULT_BLANK) -> "Machine":
        """Validate canonical headerless TSV and compile reusable integer actions."""
        if blank_symbol != DEFAULT_BLANK:
            raise MachineError("Blank symbol must be ·.")
        if not isinstance(text, str):
            raise MachineError("Machine TSV must be text.")
        source = unicodedata.normalize("NFC", text.removeprefix("\ufeff"))
        lines = source.replace("\r\n", "\n").split("\n")
        if len(lines) > 1 and lines[-1] == "":
            lines.pop()

        rows = []
        seen_curr = {}
        for line_number, line in enumerate(lines, 1):
            fields = line.split("\t")
            prefix = f"Line {line_number}: "
            if len(fields) != 5:
                raise MachineError(prefix + f"expected 5 tab-separated fields, got {len(fields)}.")
            current, read_field, move, write, next_state = fields
            if not current:
                raise MachineError(prefix + "current state is empty.")
            if current != START_STATE and not is_state_name(current):
                raise MachineError(prefix + "current state must be ⎆ or a non-reserved state name over the tape alphabet.")
            reads = tuple(dict.fromkeys(read_field.split(" ")))
            for read in reads:
                if not read:
                    raise MachineError(prefix + "current symbol is empty.")
                if not is_tape_symbol(read):
                    raise MachineError(prefix + "current symbol must be one Unicode letter, number, punctuation mark, or symbol.")
            if move not in MOVES:
                raise MachineError(prefix + f"invalid move {move!r}; expected ←, →, or ⏹.")
            if write and not is_tape_symbol(write):
                raise MachineError(prefix + "next symbol must be empty or one Unicode letter, number, punctuation mark, or symbol.")
            if not next_state:
                raise MachineError(prefix + "next state is required for every move.")
            if next_state in {START_STATE, ERROR_STATE}:
                raise MachineError(prefix + f"{next_state} may not appear in next_state.")
            if next_state == ACCEPT_STATE:
                if move != "⏹":
                    raise MachineError(prefix + "✔ may only be entered with a ⏹ move.")
            elif not is_state_name(next_state):
                raise MachineError(prefix + "next state must be a non-reserved state name over the tape alphabet, or ✔ with ⏹.")
            curr = (current, read_field)
            if curr in seen_curr:
                raise MachineError(
                    f"Duplicate rule for current state {current!r} and current-symbol field "
                    f"{read_field!r} on lines {seen_curr[curr]}, {line_number}."
                )
            seen_curr[curr] = line_number
            for read in reads:
                rows.append((current, read, write or read, next_state, move, line_number))

        halting_states = {ACCEPT_STATE, ERROR_STATE}
        halting_states.update(row[3] for row in rows if row[4] == "⏹")
        state_ids = {START_STATE: 0, ACCEPT_STATE: 1, ERROR_STATE: 2}
        symbol_ids = {DEFAULT_BLANK: 0}
        for current, read, write, next_state, move, line_number in rows:
            if current in halting_states:
                raise MachineError(f"Line {line_number}: halting state {current!r} may not appear in curr_state.")
            if next_state in halting_states and move != "⏹":
                raise MachineError(f"Line {line_number}: halting state {next_state!r} must be entered with ⏹.")
            for state in (current, next_state):
                if state not in state_ids:
                    state_ids[state] = len(state_ids)
            for symbol in (read, write):
                if symbol not in symbol_ids:
                    symbol_ids[symbol] = len(symbol_ids)

        table: list[list[Optional[Action]]] = [
            [None] * len(symbol_ids) for _ in state_ids
        ]
        matching_lines: dict[tuple[int, int], list[int]] = {}
        for current, read, write, next_state, move, line_number in rows:
            state_id, read_id = state_ids[current], symbol_ids[read]
            key = (state_id, read_id)
            matching_lines.setdefault(key, []).append(line_number)
            action = (symbol_ids[write], state_ids[next_state], MOVES[move])
            previous = table[state_id][read_id]
            if previous is None:
                table[state_id][read_id] = action
            elif previous != action:
                # Different curr strings may overlap. Preserve a conflict for
                # a runtime diagnostic rather than inventing rule precedence.
                table[state_id][read_id] = AMBIGUOUS_ACTION
        ambiguities = {
            key: tuple(line_numbers)
            for key, line_numbers in matching_lines.items()
            if table[key[0]][key[1]] is AMBIGUOUS_ACTION
        }
        statuses: list[Optional[str]] = [None] * len(state_ids)
        for state in halting_states:
            statuses[state_ids[state]] = (
                "accepted" if state == ACCEPT_STATE
                else "errored" if state == ERROR_STATE else "rejected"
            )
        warnings = () if any(row[0] == START_STATE for row in rows) else (
            f"Initial state {START_STATE} has no transition row; execution will report a missing rule.",
        )
        return cls(
            tuple(state_ids), tuple(symbol_ids), symbol_ids,
            tuple(tuple(row) for row in table), tuple(statuses),
            ambiguities, warnings,
        )

    def run(
        self, input_tape: Iterable[str] = "", *,
        max_steps: int = DEFAULT_MAX_STEPS,
        tape_storage: str = "memory", tape_directory: Optional[str] = None,
    ) -> RunResult:
        """Run normalized Unicode text or an iterable of single-symbol cells.

        Zero max_steps means unlimited execution. Use iter_normalized_characters
        for streamed text whose combining sequences may span chunk boundaries.
        Results retain the tape for streaming output; close them after use.
        """
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 0:
            raise MachineError("Maximum steps must be a non-negative integer (0 means unlimited).")
        if tape_storage not in {"memory", "disk"}:
            raise MachineError("Tape storage must be memory or disk.")
        if tape_directory is not None and tape_storage != "disk":
            raise MachineError("A tape directory requires disk storage.")
        symbols = list(self.symbols)
        symbol_ids = self.symbol_ids.copy()

        def encode() -> Iterator[int]:
            for symbol in iter_input_symbols(input_tape):
                symbol_id = symbol_ids.get(symbol)
                if symbol_id is None:
                    symbol_id = len(symbols)
                    symbol_ids[symbol] = symbol_id
                    symbols.append(symbol)
                yield symbol_id

        tape = MemoryTape() if tape_storage == "memory" else DiskTape(tape_directory)
        try:
            input_length = tape.load(encode())
            return self._execute(tape, tuple(symbols), input_length, max_steps)
        except BaseException:
            tape.close()
            raise

    def _execute(self, tape: Tape, symbols: tuple[str, ...], input_length: int, max_steps: int) -> RunResult:
        table = self.table
        symbol_count = len(self.symbols)
        state = 0
        head = 0
        steps = 0
        status = "timeout"
        message = ""
        page_index = 0
        offset = 0
        page = tape.get_page(0)
        max_written = input_length - 1

        while max_steps == 0 or steps < max_steps:
            steps += 1
            read = page[offset] if page is not None else 0
            action = table[state][read] if read < symbol_count else None
            if action is None:
                status = "errored"
                message = f"No transition for ({self.states[state]}, {symbols[read]}); no rule was applied."
                break
            if action is AMBIGUOUS_ACTION:
                status = "errored"
                lines = ", ".join(map(str, self.ambiguities[(state, read)]))
                message = (
                    f"Ambiguous transition for state {self.states[state]!r} and symbol "
                    f"{symbols[read]!r} on lines {lines}; the matching rules prescribe different actions."
                )
                break
            write, next_state, move = action
            if write != read:
                if page is None:
                    page = tape.ensure_page(page_index)
                page[offset] = write
                if head > max_written:
                    max_written = head
            state = next_state
            if move == 0:
                status = "accepted" if state == 1 else "rejected"
                break
            if move == -1 and head == 0:
                state = 2
                status = "errored"
                message = f"Cannot move left from cell 0; entered error state {ERROR_STATE}."
                break
            head += move
            offset += move
            if offset == PAGE_CELLS:
                page_index += 1
                offset = 0
                page = tape.get_page(page_index)
            elif offset < 0:
                page_index -= 1
                offset = PAGE_CELLS - 1
                page = tape.get_page(page_index)

        start, end = tape.bounds(max_written)
        return RunResult(
            status, self.states[state], steps, head, start, self.symbols[0],
            end, input_length, tape, symbols, message,
        )
