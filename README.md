# Calculate Block

A Tetris-style falling-block game where every block is a digit (`0-9`) or an
operator (`+ - * % =`). Pieces fall as **1-4 block shapes** (single, domino,
trominoes, tetrominoes) that you can **rotate**, and each cell carries its own
character. Instead of clearing full rows, you clear blocks by forming
**equations** and lining up **operators** and **numbers** — then watch the chain
reactions cascade.

Built with [pygame](https://www.pygame.org/).

## Requirements

- Python 3.8+
- `pygame`

```bash
pip install pygame
```

## Run

```bash
python calculate_game.py
```

## Controls

| Key            | Action          |
| -------------- | --------------- |
| `Left`/`Right` | Move piece      |
| `Up`           | Rotate piece    |
| `Down`         | Soft drop       |
| `Space`        | Hard drop       |
| `P`            | Pause / resume  |
| `M`            | Mute / unmute   |
| `R`            | Restart (after game over) |

## How clearing works

Shapes fall from the top. When a piece locks, the board is scanned and these
rules are applied repeatedly until nothing more clears (removals are
gravity-based and **cascade** — blocks that fall into place can trigger new
matches).

### Equations

Within each contiguous run of filled cells (gaps act as separators), every `=`
forms an equation between the segment on its left and the one on its right, so a
row with N `=` yields N candidate equations.

If **any** equation in a row evaluates equal, the **whole row is removed** and
the rows above drop down. Credit for the row is the **sum of all its number
cells' values**.

- Example: a row containing `8-4=4` (8 − 4 = 4) clears that entire row.

(Operator precedence: `*` and `%` bind tighter than `+` and `-`; operands are
non-negative integers.)

### Adjacent operators

Orthogonally adjacent operators (`+ - * % =`) get cleared:

- A **straight run** vanishes in greedy pairs (`+1` each); a leftover odd one
  stays.
- A connected operator cluster that **bends** — some operator has *both* a
  horizontal and a vertical operator neighbor (an L, T, plus, or any 2-D blob) —
  is removed **entirely** (`+N-1`).

Equations are resolved first, so a valid `=` equation is never pre-empted by the
operator rule.

### Number lines

Any straight run of **4 number cells** (horizontal, vertical, or either
diagonal) whose digits are **all identical** *or* form **3 consecutive integers**
(ascending or descending) is removed. Blocks above fall down to fill the gaps.

- Credit = (sum of the removed digits) + 100.

## Piece spawning

Pieces are drawn from a shuffled "bag" that is refilled when empty. Each bag is
split roughly **evenly between operators and digits**, and guarantees a couple of
`=` signs per bag so that multi-equation rows are achievable.

## Board & progression

- The playfield is 20 rows tall and starts **10 columns** wide.
- Leveling is **score-driven**: reaching the next threshold automatically levels
  you up. Level 2 is at **5000** points, level 3 at **10000**, and so on
  (`(level − 1) × 5000`).
- Each level-up:
  - **banks every number currently on the board** into your score,
  - **clears the whole board**,
  - **narrows the board by one column** (down to a floor of **4**), and
  - speeds up the fall.

## Audio

All audio is **synthesized at startup** — there are no audio asset files:

- **Sound effects** for move, drop, lock, equation, number line, operator clear,
  level up, and game over.
- A looping **background music** track (a short chiptune phrase) on its own
  reserved channel, so effects never cut it off.

Music pauses with the game (`P`) and stops/resumes with mute. If no audio device
is available, the game runs silently. Press `M` to mute/unmute everything.
