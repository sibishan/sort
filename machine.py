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

    def validate(self):
        halting, continuing = set(), set()
        for (st, _), (mv, _, nx) in self.rules.items():
            (halting if mv == HALT else continuing).add(nx)
            if nx in (INIT, ERROR):
                raise ValueError(f"illegal transition into {nx}")
            if mv == HALT and st in halting:
                pass
        both = halting & continuing
        if both:
            raise ValueError(f"states used both as halting and continuing: {both}")
        for (st, _) in self.rules:
            if st in halting:
                raise ValueError(f"transition out of halting state {st}")

    def to_tsv(self, explicit=False):
        self.validate()
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
