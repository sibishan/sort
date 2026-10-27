"""
Tape alphabet used:
    0-9 A-F         hex digits (input)
    g-v             marked versions of 0-F  (0->g, 1->h, ..., F->v)
    [ , ]           input punctuation
    ;               cursor: replaces the comma between the pair being compared
"""

HEX = "0123456789ABCDEF"
MARK = dict(zip(HEX, "ghijklmnopqrstuv"))      # unmarked -> marked
UNMARK = {v: k for k, v in MARK.items()}       # marked   -> unmarked
H = list(HEX)
MK = list(MARK.values())

INIT = "\u2386"    # ⎆ initial state
ACCEPT = "\u2714"  # ✔ accept state
ERROR = "\u2757"   # ❗ error state
BLANK = "\u00b7"   # · blank symbol
RIGHT = "\u2192"   # →
LEFT = "\u2190"    # ←
HALT = "\u23f9"    # ⏹

LDELIM = ["[", ","]   # symbols that can sit just left of a word's first digit

class Machine:
    def __init__(self):
        self.rules = {}   # (state, symbol) -> (move, write_or_None, next_state)

    def add(self, state, symbols, move, nxt, write=None):
        if isinstance(symbols, str):
            symbols = [symbols]
        for s in symbols:
            key, val = (state, s), (move, write, nxt)
            if key in self.rules and self.rules[key] != val:
                raise ValueError(f"conflicting rules for {key}: {self.rules[key]} vs {val}")
            self.rules[key] = val

    def to_tsv(self, explicit=False):
        lines = []
        if explicit:
            for (st, sym), (mv, wr, nx) in self.rules.items():
                lines.append("\t".join([st, sym, mv, wr if wr else sym, nx]))
        else:
            groups = {}
            for (st, sym), (mv, wr, nx) in self.rules.items():
                groups.setdefault((st, mv, wr, nx), []).append(sym)
            for (st, mv, wr, nx), syms in groups.items():
                lines.append("\t".join([st, " ".join(syms), mv, wr or "", nx]))
        return "\n".join(lines)   # grammar: rule { newline rule } -> no trailing newline
