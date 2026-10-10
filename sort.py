from machine import Machine

"""
Tape alphabet used:
    0-9 A-F         hex digits (input)
    g-v             marked versions of 0-F  (0->g, 1->h, ..., F->v)
    [ , ]           input punctuation
    ;               cursor: replaces the comma between the pair being compared
    {               swap flag: replaces '[' at cell 0 when a pass has swapped
"""

HEX = "0123456789ABCDEF"
MARK = dict(zip(HEX, "ghijklmnopqrstuv"))      # unmarked -> marked
UNMARK = {v: k for k, v in MARK.items()}         # marked   -> unmarked
H = list(HEX)
MK = list(MARK.values())

INIT = "\u2386"    # ⎆ initial state
ACCEPT = "\u2714"  # ✔ accept state
ERROR = "\u2757"   # ❗ error state
BLANK = "\u00b7"   # · blank symbol
RIGHT = "\u2192"   # →
LEFT = "\u2190"    # ←
HALT = "\u25a0"    # ■

LDELIM = ["[", "{", ","]   # symbols that can sit just left of a word's first digit

"""
!TODO: define states introduced in this program to stay on the same page
"""

m = Machine()