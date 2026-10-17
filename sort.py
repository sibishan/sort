from machine import Machine

"""
Tape alphabet used:
    0-9 A-F         hex digits (input)
    g-v             marked versions of 0-F  (0->g, 1->h, ..., F->v)
    [ , ]           input punctuation
    ;               cursor: replaces the comma between the pair being compared
    :               swap flag: indicates a swap has occured here.
    |               separator: separates the sorted and unsorted parts of the list
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

LDELIM = ["[", ",", ":"]   # symbols that can sit just left of a word's first digit

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
start_swap: pair is not in order, commence swapping, walks right and marks as it goes
start_swap_R: walks back the whole marked right input
start_swap_L: walks and marks the left input, stopping at the left delimiter
swap_middle: walks right to ';', then steps left onto the last left-word cell
find_swap: picks up the rightmost pending (marked) left cell, or finishes when it reaches the delimiter
carry_swap_L_a: carries left digit a right to the end of the right word
carry_swap_R_a: walks left to the rightmost pending right cell, writes a, picks up that cell's digit b
carry_backswap_R_b: carries b left across the right word to ';'
carry_backswap_L_b: skips finished left cells, writes b into the pending cell
swap_done: walks right to ';' and turns it into ':' (a swap happened this pass)
shrink: pass is over; walks left over the last unsorted word, then places '|' before it
check_sorted: no swap at the last boundary; scans left for any remaining ':'
restore: no swap this pass, so sorted; walks right and turns '|' back into ','
return_start: swap happened; walks left to '[' clearing every ':' back to ',', then restarts the pass
✔ (ACCEPT): the list is in order

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

# if the list only 1 argument left: Sorted 
m.add("chk", "|", LEFT, "fin", write=",")
 
# compare the pair around ';'
# return from the right word to ';'
m.add("cmp_back_R", H + MK, LEFT, "cmp_back_R")
m.add("cmp_back_R", ";", LEFT, "cmp_back_L")
# in the left word: skip unmarked digits, stop at the last mark (or the delimiter)
m.add("cmp_back_L", H, LEFT, "cmp_back_L")
m.add("cmp_back_L", MK + LDELIM, RIGHT, "cmp_find")
# first unmarked digit of the left word
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
            m.add(f"cmp_test_{d}", e, RIGHT, "start_swap", write=MARK[e])     # out of order -> swap needed.
# start_swap: If the pair is out of order, we need to swap them. 

# Starting by marking the entire left word, then the entire right word.
for a in H:
    m.add("start_swap", a, RIGHT, "start_swap", write=MARK[a])
m.add("start_swap", ["]", ",", "|"], LEFT, "start_swap_R")
# Walking back the whole marked input.
m.add("start_swap_R", MK, LEFT, "start_swap_R")
m.add("start_swap_R", ";", LEFT, "start_swap_L") 
for a in H:
    m.add("start_swap_L", a, LEFT, "start_swap_L", write=MARK[a]) 
m.add("start_swap_L", MK , LEFT, "start_swap_L") 
m.add("start_swap_L", LDELIM, RIGHT, "swap_middle")  
# return the cursor to the middle of the pair to swap, and unmark the left word.
m.add("swap_middle", MK, RIGHT, "swap_middle")
m.add("swap_middle", ";", LEFT, "find_swap")

# find_swap: Now we are at the left side of the pair to swap. We will swap the two marked words.
# Because of how find_swap is defined, find_swap only ever sees a marked cell.
m.add("find_swap", LDELIM, RIGHT, "swap_done")  # if we reach the left delimiter, we are done swapping
for a in MK:
    m.add("find_swap", a, RIGHT, f"carry_swap_L_{a}")
    m.add(f"carry_swap_L_{a}", H + MK + [";"], RIGHT, f"carry_swap_L_{a}")
    m.add(f"carry_swap_L_{a}", ["]", ",", "|"] , LEFT, f"carry_swap_R_{a}")
    m.add(f"carry_swap_R_{a}", H, LEFT, f"carry_swap_R_{a}")
    for b in MK:
        m.add(f"carry_swap_R_{a}", b, LEFT, f"carry_backswap_R_{b}", write=UNMARK[a])
    m.add(f"carry_backswap_R_{a}", MK, LEFT, f"carry_backswap_R_{a}")
    m.add(f"carry_backswap_R_{a}", ";" , LEFT, f"carry_backswap_L_{a}")
    m.add(f"carry_backswap_L_{a}", H, LEFT, f"carry_backswap_L_{a}")
    for c in MK:
        m.add(f"carry_backswap_L_{a}", c, LEFT, "find_swap", write=UNMARK[a])
# swap_done: Return the cursor to the middle of the pair, and change ";" to ":", indicating that a swap has occurred.
m.add("swap_done", H, RIGHT, "swap_done")
m.add("swap_done", ";", RIGHT, "adv", write=":")

# If there's no swap, simply unmark the pair and move on to the next pair.
# unmark the pair: right word first, then left word
m.add("clrR_IN", H, RIGHT, "clrR_IN")
for c in MK:
    m.add("clrR_IN", c, RIGHT, "clrR_IN", write=UNMARK[c])
m.add("clrR_IN", [",", "]", "|"], LEFT, "clrL_IN")
m.add("clrL_IN", H + [";"], LEFT, "clrL_IN")
for c in MK:
    m.add("clrL_IN", c, LEFT, "clrL_IN", write=UNMARK[c])
m.add("clrL_IN", LDELIM, RIGHT, "tocur_IN")
 
# walk back to ';', restore the comma, move the cursor to the next pair
m.add("tocur_IN", H, RIGHT, "tocur_IN")
m.add("tocur_IN", ";", RIGHT, "adv", write=",")
m.add("adv", H, RIGHT, "adv")
m.add("adv", ",", LEFT, "cmp_back_L", write=";")   # next pair
m.add("adv", "]", LEFT, "shrink")                       # no pairs left, the pass is done, shrink the input by 1.
m.add("adv", "|", LEFT, "shrink", write=",")            # no pairs left, the pass is done, shrink the input by 1.
m.add("shrink", H, LEFT, "shrink")
m.add("shrink", ":", LEFT, "return_start", write="|")
m.add("shrink", ",", LEFT, "check_sorted", write="|")
m.add("check_sorted", H + [","], LEFT, "check_sorted")
m.add("check_sorted", ":", LEFT, "return_start", write=",")  # if we see a swap flag, the list is not sorted yet

m.add("check_sorted", "[", RIGHT, "restore") # the list is sorted, restore the input and accept
m.add("restore", H + [","], RIGHT, "restore")
m.add("restore", "|", LEFT, "fin", write=",")

m.add("return_start", H + [",", "|"], LEFT, "return_start")
m.add("return_start", ":", LEFT, "return_start", write=",")  # clear the swap flag
m.add("return_start", "[", RIGHT, "chk")
tsv = m.to_tsv()
with open("sort.tsv", "w", encoding="utf-8", newline="") as f:
    f.write(tsv)