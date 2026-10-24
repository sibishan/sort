TM REFERENCE CHECKER AND SIMULATOR
41080 Theory of Computing Science

tm.py checks Turing machine files and runs them. It is the canonical
definition of the machine file format. The spec sheet on Canvas is a
guide to it; where the two disagree, tm.py is right.


CONTENTS

  README.txt   this file
  tm.py        the checker and simulator
  examples/    five valid machines
  broken/      seventeen invalid or questionable machine files


REQUIREMENTS

Python 3.10 or later. No other packages.

The commands below use python3. On Windows, type python or py instead.
Run them from inside this folder.


CHECKING A MACHINE FILE

  python3 tm.py examples/even-ones.tsv

prints

  examples/even-ones.tsv: valid, 9 transitions

A file with problems gets a list of them, ordered by line:

  python3 tm.py broken/11-reserved-states.tsv

  broken/11-reserved-states.tsv: invalid
    error: line 1: only a halt (⏹) can enter ✔
    error: line 2: next state cannot be ❗
    error: line 3: next state cannot be ⎆
    error: line 4: current state cannot be ✔

An error makes the file invalid. A warning reports something tm.py
repaired, such as an empty line it skipped; the file is still valid.
tm.py exits with status 0 for a valid file and 1 for an invalid one.

Run tm.py on each file in broken/ to see the kinds of report it gives.


RUNNING A MACHINE

Put one or more initial tapes after the file name:

  python3 tm.py examples/balanced.tsv '(())' '(()'

  examples/balanced.tsv: valid, 15 transitions
  '(())': ✔ after 17 steps, tape '|xxx'
  '(()': unmatched-open after 9 steps, tape '[xx'

Each line gives the state the machine halted in, the number of steps,
and the final tape with trailing blanks removed.

Put each tape in quotes, as above, so the shell passes it unchanged.
An empty tape is ''. In the Windows Command Prompt, use double quotes
instead: "(())" and "". To put a blank on the tape, type · (U+00B7).

The machine runs on any tape you give it. tm.py does not check tapes.

A run stops after 1,000,000 steps unless it halts first. It then
reports "still running". Change the limit with --max-steps:

  python3 tm.py examples/anbncn.tsv aaabbbccc --max-steps 20

  examples/anbncn.tsv: valid, 30 transitions
  'aaabbbccc': still running after 20 steps, tape 'AAaBBbCCc'


TRACES

--trace prints every configuration: the step count, the state, and the
tape, starting from step 0.

  python3 tm.py examples/balanced.tsv '()' --trace

In a terminal, the cell under the head is shown in reverse video. When
the output goes to a file or another program, a ^ on the next line marks
the head instead:

  python3 tm.py examples/balanced.tsv '()' --trace > trace.txt

trace.txt then begins:

  examples/balanced.tsv: valid, 15 transitions

     step  state            tape
        0  ⎆                ()
                            ^
        1  find-close       [)
                             ^

On Windows, reverse video needs Windows Terminal (the default terminal
on Windows 11). In older consoles it shows up as codes like [7m. Send
the output to a file instead.


WHAT TM.PY CHECKS

A tape symbol is a single Unicode character in general category L, N,
P or S, other than the blank ·. A state name is one or more tape
symbols, other than the reserved names ⎆, ✔ and ❗.

Whole file:
  - The file must be UTF-8, in Unicode normal form NFC.
  - A byte-order mark at the start is ignored, with a warning.
  - Line endings may be LF or CRLF. A final newline is optional.
  - Empty lines are ignored, with a warning.
  - An empty file is valid. Every tape takes it straight to ❗.

Each line is one rule, with exactly five tab-separated fields:
  1. current state    ⎆ or a state name
  2. current symbols  one or more symbols separated by single spaces;
                      each a tape symbol or the blank. A symbol listed
                      twice gets a warning.
  3. move             → ← or ⏹
  4. next symbol      empty (leave the cell unchanged), or one tape
                      symbol or the blank
  5. next state       a state name, or ✔ if the move is ⏹

There is no quoting. A " is an ordinary tape symbol.

Across rules:
  - No two rules share a current state and a current symbol.
  - A state entered by ⏹ is a halting state. No rule may enter it
    with → or ←, and no rule may have it as the current state.

Each step counts, reads, writes, updates the state and moves, in that
order. With no rule for the current state and symbol, the machine goes
to ❗ and writes nothing. A ← from cell 0 goes to ❗ after the write.

Unicode adds characters over time, and tm.py uses the character data of
the Python that runs it. A character too new for your Python counts as
not a tape symbol.


USING TM.PY FROM PYTHON

  import tm

  machine, warnings = tm.load("examples/even-ones.tsv")
  final = tm.run(machine, "0110")
  print(final.state, final.steps, final.tape)

  for config in tm.trace(machine, "0110"):
      print(config)

tm.load raises tm.InvalidMachine for an invalid file; its .problems
attribute lists the problems. Each configuration has the fields state,
tape, head, steps and halted. Its tape includes every cell the head
has visited, blanks too; tm.tape_string(config) drops trailing blanks.


THE FILES

examples/
  even-ones.tsv     accepts binary strings with an even number of 1s
  increment.tsv     adds 1 to a little-endian binary number
  palindrome.tsv    accepts palindromes over a and b
  balanced.tsv      accepts balanced strings of ( and )
  anbncn.tsv        accepts a^n b^n c^n

broken/
  01  file is not UTF-8
  02  a character that looks like the blank but is not
  03  byte-order mark (warning only)
  04  header row
  05  spaces instead of tabs
  06  empty next-symbol field left out
  07  empty lines (warnings only)
  08  a " saved with spreadsheet quoting
  09  moves written as R, L and H
  10  multi-character symbols and a doubled space
  11  misused reserved states
  12  blank inside a state name
  13  symbol listed twice in a rule (warnings only)
  14  two rules for the same state and symbol
  15  a state entered by both a halt and a move
  16  a rule for a halting state
  17  several of the above
