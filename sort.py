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
HALT = "\u23f9"    # ⏹

LDELIM = ["[", "{", ","]   # symbols that can sit just left of a word's first digit

"""
STATES
⎆ (INIT): starts at cell 0 and steps into the list
chk: scans right to check whether the list has two or more entries
fin: walks back to cell 0 and accepts
cmp_back_R: walks left out of the right word to ';'
cmp_back_L: walks left to the next digit to compare in the left word
cmp_find: marks the next left-word digit, or detects that the words are equal
cmp_carry_d: carries digit d right to ';'
cmp_test_d: compares d with the next right-word digit
clrR_IN: unmarks the right word
clrL_IN: unmarks the left word
tocur_IN: walks back to ';' and restores it to ','
adv: moves the cursor to the next pair, or ends the check
✔ (ACCEPT): the list is in order
not_sorted: a pair is out of order

!TODO: define states introduced in this program to stay on the same page
"""

m = Machine()
idx = HEX.index
 
# start, handle empty list & single element list
m.add(INIT, "[", RIGHT, "chk")
m.add("chk", H, RIGHT, "chk")
m.add("chk", "]", LEFT, "fin")
m.add("chk", ",", LEFT, "cmp_back_L", write=";")
m.add("fin", H + [","], LEFT, "fin")
m.add("fin", "[", HALT, ACCEPT)
 
# compare the pair around ';'
# return from the right word to ';'
m.add("cmp_back_R", H + MK, LEFT, "cmp_back_R")
m.add("cmp_back_R", ";", LEFT, "cmp_back_L")
# in the left word: skip unmarked digits, stop at the last mark (or the delimiter)
m.add("cmp_back_L", H, LEFT, "cmp_back_L")
m.add("cmp_back_L", MK + ["[", ","], RIGHT, "cmp_find")
# first unmarked digit of the left word
m.add("cmp_find", MK, RIGHT, "cmp_find")
m.add("cmp_find", ";", RIGHT, "clrR_IN")
for d in H:
    m.add("cmp_find", d, RIGHT, f"cmp_carry_{d}", write=MARK[d])
    m.add(f"cmp_carry_{d}", H + MK, RIGHT, f"cmp_carry_{d}")
    m.add(f"cmp_carry_{d}", ";", RIGHT, f"cmp_test_{d}")
    m.add(f"cmp_test_{d}", MK, RIGHT, f"cmp_test_{d}")
    for e in H:
        if d == e:
            m.add(f"cmp_test_{d}", e, LEFT, "cmp_back_R", write=MARK[e])  # equal -> next digit
        elif idx(d) < idx(e):
            m.add(f"cmp_test_{d}", e, RIGHT, "clrR_IN")       # in order
        else:
            m.add(f"cmp_test_{d}", e, HALT, "not_sorted")     # out of order -> reject
 
# unmark the pair: right word first, then left word
m.add("clrR_IN", H, RIGHT, "clrR_IN")
for c in MK:
    m.add("clrR_IN", c, RIGHT, "clrR_IN", write=UNMARK[c])
m.add("clrR_IN", [",", "]"], LEFT, "clrL_IN")
m.add("clrL_IN", H + [";"], LEFT, "clrL_IN")
for c in MK:
    m.add("clrL_IN", c, LEFT, "clrL_IN", write=UNMARK[c])
m.add("clrL_IN", ["[", ","], RIGHT, "tocur_IN")
 
# walk back to ';', restore the comma, move the cursor to the next pair
m.add("tocur_IN", H, RIGHT, "tocur_IN")
m.add("tocur_IN", ";", RIGHT, "adv", write=",")
m.add("adv", H, RIGHT, "adv")
m.add("adv", ",", LEFT, "cmp_back_L", write=";")   # next pair
m.add("adv", "]", LEFT, "fin")                     # no pairs left -> go home, accept

tsv = m.to_tsv()
with open("sort.tsv", "w", encoding="utf-8", newline="") as f:
    f.write(tsv)