"""Command line interface, kept separate from the simulation loop."""

import argparse
import json
from pathlib import Path
import sys

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from runner.cli import main

    raise SystemExit(main())

from .simulator import DEFAULT_MAX_STEPS, Machine, MachineError, RunResult
from .symbols import iter_input_symbols, iter_normalized_characters

EXAMPLES = Path(__file__).resolve().parent / "examples"


class RunnerArgumentParser(argparse.ArgumentParser):
    """Use code 1 for usage errors, reserving code 2 for machine-file failures."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _non_negative_integer(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from error
    if number < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return number


def _read_machine(name: str) -> str:
    if name == "-":
        _configure_utf8_stdin()
        return sys.stdin.read()
    path = Path(name).expanduser()
    if not path.is_file():
        # Examples travel with this package and resolve independently of the cwd.
        example = EXAMPLES / (name if name.endswith(".tsv") else name + ".tsv")
        if Path(name).name == name and example.is_file():
            path = example
        else:
            raise MachineError(f"Machine {name!r} not found. Use a TSV path or --list-machines.")
    with path.open(encoding="utf-8", newline="") as source:
        return source.read()


def _configure_utf8_stdin() -> None:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict", newline="")


def _configure_utf8_output() -> None:
    # Redirected streams may use a legacy encoding, particularly on Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict", newline="")


def _input_tokens(value: str) -> list[str]:
    try:
        tokens = json.loads(value)
    except json.JSONDecodeError as error:
        raise MachineError(f"Invalid token input {value!r}: {error.msg}.") from error
    if not isinstance(tokens, list) or any(not isinstance(token, str) or not token for token in tokens):
        raise MachineError("With --tokens, each input must be a JSON array of single-symbol strings.")
    return tokens


def _file_symbols(name: str, as_tokens: bool):
    """Normalize streamed UTF-8 text, or read one explicit JSON cell per line."""
    if name == "-":
        stream = sys.stdin
        _configure_utf8_stdin()
    else:
        stream = open(Path(name).expanduser(), encoding="utf-8", newline="")
    try:
        if as_tokens:
            for line_number, line in enumerate(stream, 1):
                try:
                    token = json.loads(line)
                except json.JSONDecodeError as error:
                    raise MachineError(f"Input token line {line_number}: {error.msg}.") from error
                if not isinstance(token, str) or not token:
                    raise MachineError(f"Input token line {line_number}: expected a single-symbol JSON string.")
                yield token
        else:
            yield from iter_normalized_characters(iter(lambda: stream.read(65_536), ""))
    finally:
        if name != "-":
            stream.close()


def _write_json_string(stream, chunks) -> None:
    stream.write('"')
    for chunk in chunks:
        stream.write(json.dumps(chunk, ensure_ascii=False)[1:-1])
    stream.write('"')


def _token_batches(result: RunResult):
    """Bound batches by both symbol count and text size."""
    batch = []
    length = 0
    for token in result.iter_tokens():
        if batch and (len(batch) == 4096 or length + len(token) > 65_536):
            yield batch
            batch = []
            length = 0
        batch.append(token)
        length += len(token)
        if length >= 65_536:
            yield batch
            batch = []
            length = 0
    if batch:
        yield batch


def _long_token_chunks(token: str):
    for position in range(0, len(token), 65_536):
        yield token[position:position + 65_536]


def _write_json_tokens(stream, result: RunResult) -> None:
    stream.write("[")
    first = True
    for chunk in _token_batches(result):
        if not first:
            stream.write(",")
        if len(chunk) == 1 and len(chunk[0]) > 65_536:
            _write_json_string(stream, _long_token_chunks(chunk[0]))
        else:
            stream.write(json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))[1:-1])
        first = False
    stream.write("]")


def _write_tape(stream, result: RunResult, output_format: str) -> None:
    if output_format == "text":
        for chunk in result.iter_text_chunks():
            stream.write(chunk)
    else:
        for chunk in _token_batches(result):
            if len(chunk) == 1 and len(chunk[0]) > 65_536:
                _write_json_string(stream, _long_token_chunks(chunk[0]))
                stream.write("\n")
            else:
                stream.write("\n".join(json.dumps(token, ensure_ascii=False) for token in chunk) + "\n")


def _print_result(result: RunResult, description: dict, args, warnings: tuple[str, ...] = ()) -> None:
    if args.tape_only:
        if args.output_file is None or args.output_file == "-":
            _write_tape(sys.stdout, result, "text" if args.output_file is None else args.output_format)
            sys.stdout.flush()
        else:
            with open(Path(args.output_file).expanduser(), "w", encoding="utf-8", newline="") as output:
                _write_tape(output, result, args.output_format)
        return

    metadata = {**description, **result.to_dict(include_tape=False)}
    if warnings:
        metadata["warnings"] = list(warnings)
    stream = sys.stderr if args.output_file == "-" else sys.stdout
    if args.output_file is not None:
        if args.output_file == "-":
            _write_tape(sys.stdout, result, args.output_format)
            sys.stdout.flush()
        else:
            with open(Path(args.output_file).expanduser(), "w", encoding="utf-8", newline="") as output:
                _write_tape(output, result, args.output_format)
        metadata.update(outputFile=args.output_file, outputFormat=args.output_format)

    if args.json:
        stream.write(json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))[:-1])
        if args.output_file is None:
            stream.write(',"finalTape":')
            _write_json_string(stream, result.iter_text_chunks())
            stream.write(',"finalTapeTokens":')
            _write_json_tokens(stream, result)
        stream.write("}\n")
    else:
        label = "Input file" if "inputFile" in description else "Input"
        stream.write(
            f"{label}: {json.dumps(next(iter(description.values())), ensure_ascii=False)}\n"
            f"Status: {result.status}\n"
            f"Final state: {result.final_state}\n"
            f"Steps: {result.steps}\n"
            f"Head position: {result.head_position}\n"
            f"Input length: {result.input_length}\n"
            f"Tape start: {result.tape_start}\n"
            f"Tape length: {result.tape_length}\n"
        )
        if result.message:
            stream.write(f"Message: {result.message}\n")
        if args.output_file is not None:
            stream.write(f"Tape file: {args.output_file} ({args.output_format})\n")
        else:
            stream.write("Tape: ")
            _write_json_string(stream, result.iter_text_chunks())
            stream.write("\nTape tokens: ")
            _write_json_tokens(stream, result)
            stream.write("\n")
    stream.flush()


def _main(argv: list[str] | None = None) -> int:
    _configure_utf8_output()
    parser = RunnerArgumentParser(
        description="Run a Turing machine without animation. Load one machine and run one or more tapes.",
        epilog="Examples: python3 -m runner -m machine.tsv 111; "
        "python3 -m runner -m machine.tsv --json 010 101",
    )
    parser.add_argument("inputs", nargs="*", help="initial tape strings; each character is a symbol (default: empty tape)")
    parser.add_argument("-m", "--machine", help="TSV path, bundled example name, or - to read TSV from stdin")
    parser.add_argument("--list-machines", action="store_true", help="list bundled example names and exit")
    parser.add_argument("--max-steps", type=_non_negative_integer, default=DEFAULT_MAX_STEPS, help="step limit per input; 0 means unlimited (default: 1000000)")
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument("--json", action="store_true", help="print one JSON object per input, suitable for shell scripts")
    output_mode.add_argument("--tape-only", action="store_true", help="print only the final tape, without labels, metadata, or an added newline")
    parser.add_argument("--tokens", action="store_true", help="interpret each input as a JSON array of tape symbols")
    parser.add_argument("--input-file", help="read one tape from a UTF-8 file or - for stdin; with --tokens, use one JSON string per line")
    parser.add_argument("--output-file", help="stream the final tape to a UTF-8 file or - for stdout; --tape-only suppresses result metadata")
    parser.add_argument("--output-format", choices=("text", "tokens"), default="text", help="file output as concatenated text or one JSON string per symbol (default: text)")
    parser.add_argument("--tape-storage", choices=("memory", "disk"), default="memory", help="compact memory pages or a temporary memory-mapped file (default: memory)")
    parser.add_argument("--tape-dir", help="directory for disk-backed temporary tape storage")
    args = parser.parse_args(argv)
    if args.list_machines:
        for path in sorted(EXAMPLES.glob("*.tsv")):
            print(path.stem)
        return 0
    if args.machine is None:
        parser.error("--machine is required (use a saved TSV path or --list-machines)")
    if args.input_file is not None and args.inputs:
        parser.error("use either input arguments or --input-file")
    if args.input_file == "-" and args.machine == "-":
        parser.error("the machine and input tape cannot both read from stdin")
    if args.output_file is not None and len(args.inputs) > 1:
        parser.error("--output-file requires a single input tape")
    if args.output_format != "text" and args.output_file is None:
        parser.error("--output-format tokens requires --output-file")
    if args.tape_dir is not None and args.tape_storage != "disk":
        parser.error("--tape-dir requires --tape-storage disk")

    try:
        machine = Machine.from_tsv(_read_machine(args.machine))
    except (MachineError, OSError, UnicodeError) as error:
        parser.exit(2, f"error: {error}\n")

    try:
        if not args.json and not args.tape_only:
            for warning in machine.warnings:
                print(f"warning: {warning}", file=sys.stderr)
        if args.input_file is not None:
            tapes = [_file_symbols(args.input_file, args.tokens)]
            descriptions = [{"inputFile": args.input_file}]
        else:
            inputs = args.inputs or (["[]"] if args.tokens else [""])
            # Validate all argument inputs before executing or emitting results.
            tapes = [_input_tokens(value) for value in inputs] if args.tokens else inputs
            for tape in tapes:
                for _ in iter_input_symbols(tape):
                    pass
            descriptions = [{"input": tape} for tape in tapes]
        exit_code = 0
        for index, (tape, description) in enumerate(zip(tapes, descriptions)):
            if index and not args.json:
                print()
            with machine.run(
                tape, max_steps=args.max_steps, tape_storage=args.tape_storage,
                tape_directory=args.tape_dir,
            ) as result:
                _print_result(result, description, args, machine.warnings)
                if result.status != "accepted":
                    exit_code = 1
        return exit_code
    except (MachineError, OSError, UnicodeError) as error:
        parser.exit(1, f"error: {error}\n")


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
