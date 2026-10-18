# Runner usage guide

Run a Turing machine from a TSV file and inspect its final tape, state, and
execution count. The runner can execute one input, run several inputs against
one loaded machine, or be called from your own test script.

## Setup and first run

Copy the entire `runner` folder to a computer with **Python 3.10 or newer**.
It uses only the standard library: no installation, pip packages, Node.js,
or other repository files are required. All text files and CLI streams use UTF-8.

From the folder containing `runner`, run the included append-one machine:

```bash
python3 -m runner --machine append_one --tape-only 111
```

This prints exactly `1111`, with no trailing newline, and exits with code `0`.
The machine scans a unary input and appends one `1`.

You can also run the folder from any working directory:

```bash
python3 /path/to/runner --machine /path/to/my_machine.tsv --tape-only 111
```

From inside `runner`, use `python3 . --machine append_one --tape-only 111`.
Direct launches through `runner/__main__.py`, `runner/cli.py`, or
`runner/simulator.py` also accept the same arguments. In an IDE, select one
of those scripts and set its arguments, for example
`--machine append_one --json 111`.

On Windows, replace `python3` with `py -3` and use your Windows file paths.
The shell examples below use Bash syntax.

## Choose a machine

Use `--machine` (or `-m`) with a TSV file path:

```bash
python3 -m runner --machine ./my_machine.tsv 111
```

Relative machine, input, and output paths are resolved from your current working
directory. A file path takes precedence over a bundled example with the same name.

The bundled `append_one` example lives in `runner/examples/append_one.tsv`.
Bundled names resolve independently of the working directory:

```bash
python3 -m runner --list-machines
python3 -m runner --machine append_one 111
```

Add other machine TSVs to `runner/examples` to use them by name. Listing names
does not validate their files. Older files in the repository's `examples/machines`
still need a separate notation migration; `append_one.tsv` uses the current notation.

Use `--machine -` to read a definition from stdin:

```bash
python3 -m runner --machine - --tape-only 111 < my_machine.tsv
```

## Supply inputs

Each positional argument is a separate initial tape. Plain input has no
separators: `001` occupies three cells, and a comma is a literal symbol.
No start or end markers are inserted automatically.

```bash
# One input.
python3 -m runner --machine append_one 111

# Three independent runs, including an empty tape.
python3 -m runner --machine append_one '' 1 111

# No input argument also means an empty tape.
python3 -m runner --machine append_one
```

Multiple inputs work in every output mode; `--json` is optional. The runner
loads the machine once, starts each input in a fresh state with a fresh tape,
and emits results in input order. A rejection, execution error, or timeout does
not prevent later inputs from running. All positional inputs are validated
before any execution or result output.

Text is normalized to Unicode NFC before being split into cells. Each cell must
be a single Unicode letter, number, punctuation mark, or symbol. The reserved
blank `·`, whitespace, newlines, and control characters are invalid in input.
A valid input symbol need not appear in the machine's rules; execution will
report a missing rule if it reaches an undefined state/symbol pair.

Quote shell metacharacters. Put `--` before an input beginning with `-`:

```bash
python3 -m runner --machine my_machine.tsv --tape-only -- '-1'
```

### Read one tape from a file or stdin

`--input-file` reads one complete tape, not a collection of test cases. Create
a file without an added newline:

```bash
printf '%s' '111' > input.txt
python3 -m runner --machine append_one --input-file input.txt --tape-only
printf '%s' '111' | python3 -m runner --machine append_one --input-file - --tape-only
```

The file is streamed and normalized across read boundaries. Whitespace is
rejected rather than trimmed, including a trailing newline or BOM. An empty
file means an empty tape. You cannot combine `--input-file` with positional
inputs, or read both the machine and tape from stdin in one invocation.

### Supply explicit tape cells

`--tokens` changes the input representation to a JSON array of strings. It is
independent of the output format, so it also works with `--tape-only`:

```bash
python3 -m runner --machine append_one --tokens --tape-only '["1","1"]'
```

This prints `111`. Each string must normalize to exactly one allowed, nonblank
code point. `"red"` is invalid as one cell. Normalization is applied to each
cell separately; characters from different cells are never composed together.

With `--tokens --input-file`, use one JSON string per line, rather than one
JSON array for the whole file:

```bash
printf '"1"\n"1"\n' > input.jsonl
python3 -m runner --machine append_one --tokens --input-file input.jsonl --tape-only
```

Those line endings separate records and are not tape cells.

## Choose the output format

### Human-readable output

Without an output flag, each run prints its input, status, final state, action
count, head position, input length, tape bounds, and final tape. Execution errors
also include a message. This is useful for inspecting a run interactively:

```bash
python3 -m runner --machine append_one 111
```

### Tape only

Use `--tape-only` for just the final tape, without labels, metadata, warnings,
or an added trailing newline:

```bash
python3 -m runner --machine append_one --tape-only 111
```

An empty final tape prints no characters. Multiple inputs produce tape results
separated by a single newline. A rejected, errored, or timed-out execution still
returns its final tape and exits with code `1`.

### JSON results and multiple inputs

Use `--json` when your script needs structured results, including the status,
head position, and action count:

```bash
python3 -m runner --machine append_one --json '' 1 111
```

The output is **JSON Lines**: one complete object on each line, in input order,
with no enclosing JSON array. The command above produces:

```json
{"input":"","status":"accepted","finalState":"✔","steps":1,"finalHeadPosition":0,"finalTapeStart":0,"finalTapeLength":1,"inputLength":0,"blankSymbol":"·","finalTape":"1","finalTapeTokens":["1"]}
{"input":"1","status":"accepted","finalState":"✔","steps":2,"finalHeadPosition":1,"finalTapeStart":0,"finalTapeLength":2,"inputLength":1,"blankSymbol":"·","finalTape":"11","finalTapeTokens":["1","1"]}
{"input":"111","status":"accepted","finalState":"✔","steps":4,"finalHeadPosition":3,"finalTapeStart":0,"finalTapeLength":4,"inputLength":3,"blankSymbol":"·","finalTape":"1111","finalTapeTokens":["1","1","1","1"]}
```

Each object describes one run. `status` is `accepted`, `rejected`, `errored`,
or `timeout`. Execution errors include a `message`; machine warnings appear
in a `warnings` array. File input uses `inputFile` instead of `input`.
With `--tokens`, `input` contains the supplied array of cells.

The runner executes inputs but does not compare them with expected answers.
Your test script performs those comparisons. JSON is useful when you need to
check the reason for failure, rather than only the tape and exit code.
`--json` and `--tape-only` cannot be combined.

### Write the tape to a file

`--output-file` writes the tape separately and requires a single input:

```bash
python3 -m runner --machine append_one --input-file input.txt \
  --output-file output.txt --tape-only
```

The file is overwritten with the final tape. Text output has no added newline.
Without `--tape-only`, result metadata still goes to stdout. In JSON mode, the
object includes `outputFile` and `outputFormat` instead of the inline
`finalTape` and `finalTapeTokens` fields.

For one JSON string per cell, use `--output-format tokens`:

```bash
python3 -m runner --machine append_one --output-file output.jsonl \
  --output-format tokens --tape-only 11
```

This writes three lines, each containing `"1"`. `--output-format` requires
`--output-file`; its default is `text`.

Use `--output-file -` to send the tape to stdout. Metadata then goes to stderr;
`--tape-only` suppresses it. This also lets you stream token output to stdout.

### Tape bounds and output streams

Final tape output trims leading and trailing blanks while preserving internal
blanks. JSON's `finalTapeStart` gives the original position of the first returned
cell, or `0` for an entirely blank tape. `finalTapeLength` counts returned cells.
`finalTape` concatenates them; `finalTapeTokens` contains the individual cells.

**stdout** carries normal results or the tape. **stderr** carries error messages
and, in human-readable mode, warnings. With `--output-file -`, stderr also carries
metadata unless suppressed by `--tape-only`. Invalid arguments, input tapes, and
machine files are reported as text on stderr even when `--json` is selected.
For example, save results and diagnostics separately:

```bash
python3 -m runner --machine append_one --json 111 > results.jsonl 2> errors.txt
```

## Exit codes

Exit codes are process statuses, not extra text printed with the tape. They
apply to human-readable, JSON, tape-only, and file output alike.

| Code | Meaning |
| --- | --- |
| `0` | Every requested input halted and accepted in `✔`. |
| `1` | A valid machine rejected, errored, or timed out. This includes moving left of cell 0, a missing rule, or conflicting matching actions. Invalid CLI arguments, invalid input tapes, input/output-file errors, and Ctrl+C also use `1`. |
| `2` | The machine TSV is invalid or unreadable: for example malformed rows, invalid moves or symbols, forbidden states, duplicate rules, inconsistent halting states, invalid UTF-8, or a missing machine file. |

For multiple inputs, `0` means all accepted; any unsuccessful run makes the
overall code `1`, even if a later run accepts. An invalid TSV gives `2` before
any inputs run or any output file is written. An unreadable machine file also
gives `2`. The utility commands `--help` and `--list-machines` return `0` on success.

## Automate tests with Bash, without JSON

You can write a Bash script that supplies inputs and runs the module once per
input. Use `--tape-only` to capture the tape and check the exit code separately.
This also gives each test its own process status, whereas a multi-input command
returns one aggregate status.

Save this as `test_append_one.sh` in the folder containing `runner`, then run
`bash test_append_one.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

inputs=('' '1' '111' '0')
expected_tapes=('1' '11' '1111' '0')
expected_codes=(0 0 0 1)
failures=0

for i in "${!inputs[@]}"; do
    # The if statement lets us capture unsuccessful runs even with set -e.
    if actual_tape=$(python3 -m runner --machine append_one --max-steps 1000 \
        --tape-only -- "${inputs[$i]}"); then
        actual_code=0
    else
        actual_code=$?
    fi

    if (( actual_code == 2 )); then
        printf 'Machine TSV is invalid or unreadable; stopping tests.\n' >&2
        exit 2
    fi

    if [[ "$actual_tape" == "${expected_tapes[$i]}" ]] &&
        (( actual_code == expected_codes[i] )); then
        printf 'PASS input=%q\n' "${inputs[$i]}"
    else
        printf 'FAIL input=%q: expected tape=%q code=%s; got tape=%q code=%s\n' \
            "${inputs[$i]}" "${expected_tapes[$i]}" "${expected_codes[$i]}" \
            "$actual_tape" "$actual_code" >&2
        failures=$((failures + 1))
    fi
done

if (( failures > 0 )); then
    exit 1
fi
printf 'All %s tests passed.\n' "${#inputs[@]}"
```

The first three inputs accept. For `0`, this particular machine has no matching
rule: it returns the unchanged tape `0` and exit code `1`. The script checks
both results and handles that expected failure. Edit the three arrays and machine
argument for your own tests. Set the action limit to suit your machine.

For a copied runner elsewhere, replace `python3 -m runner` with
`python3 /path/to/runner`. JSON is not required for this approach. Use JSON
when you also want to assert fields such as `status`, `steps`, or `finalState`.

## Limits and tape storage

`--max-steps` limits actions per input. The default is `1000000`. If the limit
is reached before a halt, the result is `timeout` and the exit code is `1`.
A halt on the final allowed action takes precedence. Use `--max-steps 0` for
unlimited execution.

Memory storage is the default and is suitable for ordinary runs and tests.
For tapes too large to keep comfortably in RAM, `--tape-storage disk` uses a
temporary memory-mapped file so the operating system can page the tape.
`--tape-dir` chooses an existing directory for that temporary file; otherwise
the system temporary directory is used. Storage is released after each result.

```bash
python3 -m runner --machine my_machine.tsv --input-file input.txt \
  --output-file output.txt --tape-only --tape-storage disk --max-steps 0
```

Input and output files are streamed in bounded chunks. JSON without
`--output-file` includes the tape as both text and individual cells; use file
output when you want to keep large tape data out of the metadata.

## Parameter reference

Display built-in help with `python3 -m runner --help`.

| Parameter | Purpose and default |
| --- | --- |
| `inputs` | Zero or more positional tape strings; each is a separate run. Omitted input means an empty tape. With `--tokens`, each argument is a JSON array of cells. |
| `-h`, `--help` | Show usage and exit. |
| `-m`, `--machine PATH_OR_NAME` | Required for execution. Load a UTF-8 TSV path, a bundled example name, or `-` for stdin. |
| `--list-machines` | List TSV names from `runner/examples` and exit; no `--machine` required. |
| `--max-steps N` | Nonnegative action limit per input; default `1000000`, `0` means unlimited. |
| `--tape-only` | Emit only the final tape; mutually exclusive with `--json`. |
| `--json` | Emit one JSON result object per input, one object per line. |
| `--tokens` | Parse positional inputs as JSON arrays of cells, or input-file records as one JSON string per line. Does not select an output format. |
| `--input-file PATH` | Read one tape from a UTF-8 file, or `-` for stdin. Cannot be combined with positional inputs. |
| `--output-file PATH` | Write the final tape to a UTF-8 file, or `-` for stdout. Requires a single input. |
| `--output-format text\|tokens` | Tape file representation; default `text`. `tokens` writes one JSON string per cell per line. Requires `--output-file`. |
| `--tape-storage memory\|disk` | Tape storage backend; default `memory`. |
| `--tape-dir PATH` | Existing directory for temporary disk storage; requires `--tape-storage disk`. |
| `--` | End CLI option parsing so subsequent arguments can begin with `-`. |

## Write and validate a machine TSV

Save the following as `my_machine.tsv`. Separate fields with literal tabs,
including the empty fourth field where the current symbol should be preserved:

```tsv
⎆	1	→		scan
⎆	·	⏹	1	✔
scan	1	→		scan
scan	·	⏹	1	✔
```

Each rule has exactly five fields, in this order:

```text
current state    current symbol    move    next symbol    next state
```

The loader validates the entire file, including unreachable rules, before
execution. Invalid machine definitions produce exit code `2`.

- Files must be valid UTF-8. NFC normalization occurs before validation. A
  leading BOM, LF or CRLF line endings, and one final newline are accepted.
- Headers, comment rows, and empty rules are invalid. Quotes and `#` are literal
  characters; CSV quoting and field trimming are not used.
- Tape symbols are single Unicode code points in categories L, N, P, or S,
  with `·` reserved as the fixed blank. State names are nonempty words over
  that alphabet, excluding the exact reserved names `⎆`, `✔`, and `❗`.
- Current state may be an ordinary state name or `⎆`. Current symbol may be a
  list separated by single ASCII spaces. Repetitions inside one list are valid.
- Moves are `←`, `→`, and `⏹`. Next state is always required; an empty
  next-symbol field preserves the read symbol. Writing `·` erases a cell.
- `⎆` and `❗` cannot be next states. `✔` can only be entered by `⏹`.
  A halting state cannot have outgoing rules or continuing incoming rules.
- Two different rules with identical complete `curr` strings (current state
  and full current-symbol field) are invalid, even when their actions agree.
- Different symbol lists may overlap. Equivalent matching actions execute
  once. Conflicting matching actions report an execution error when reached,
  without changing state, head position, or tape; the file itself remains valid.

Execution starts in `⎆` at cell 0 with count 0. Each action increments the
counter before reading, writing, updating state, and moving. `⏹` stops
immediately: `✔` accepts and any other named halting state rejects. Moving
left from cell 0 applies the write, enters `❗`, and stops with status
`errored` and head position 0.

A missing rule reports an execution error without inventing a transition or
state. Its count phase still increments the counter. `✘` is an ordinary state
name. No start-state rule is required for file validity; its absence produces
a warning and execution then reports a missing rule. These execution failures
use exit code `1`.

The legacy `--blank` and `--column-order` options have been removed. Use the
fixed blank `·` and the column order above.

## Use the Python API

With the folder containing `runner` on your Python import path:

```python
from pathlib import Path
from runner import Machine

machine = Machine.from_tsv(Path("my_machine.tsv").read_text(encoding="utf-8"))
with machine.run("111") as result:
    print(result.status)
    print(result.to_dict())
```

The API returns a `RunResult`; process exit codes belong to the CLI. Invalid
machine definitions or input tapes raise `MachineError`. Use the context manager
to release tape storage after reading the result.

For streamed text, normalize across chunks before supplying individual cells:

```python
from runner import iter_normalized_characters

with open("input.txt", encoding="utf-8", newline="") as source:
    chunks = iter(lambda: source.read(65_536), "")
    with machine.run(iter_normalized_characters(chunks), max_steps=0,
                     tape_storage="disk") as result:
        with open("output.txt", "w", encoding="utf-8", newline="") as output:
            output.writelines(result.iter_text_chunks())
        print(result.to_dict(include_tape=False))
```

`to_dict()` and `tape_tokens` materialize the tape and are intended for small
results. Use `iter_tokens()` or `iter_text_chunks()` for large results.

## Run the project's regression tests

These commands require the full repository, unlike the standalone runner:

```bash
python3 -m unittest discover -s tests/runner -v
```

Run all browser and Python checks with `npm test`. The Python suite includes
checks that copy only `runner` into an isolated directory and exercise the CLI
and API without installed packages. Browser parity tests use Node.js when
available; the runner itself has no external dependencies.
