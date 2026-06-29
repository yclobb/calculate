import array
import asyncio
import logging
import math
import os
import random
import sys
import pygame

log = logging.getLogger("calculate_game")


def setup_logging():
    if log.handlers:
        return
    debug = bool(os.environ.get("CALC_DEBUG"))
    log.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(console)
    if debug:
        file_handler = logging.FileHandler("calculate_game.log", mode="w", encoding="utf-8")
        file_handler.setFormatter(fmt)
        log.addHandler(file_handler)
        log.debug("debug logging enabled -> calculate_game.log")


GRID_ROWS = 20
CELL = 32
FRAME = 16
HUD_W = 6 * CELL

MIN_WIDTH = 4   
MAX_WIDTH = 10  

BG = (18, 18, 24)
FRAME_COLOR = (90, 90, 110)
GRID_LINE = (35, 35, 45)
NUM_COLOR = (70, 130, 220)
OP_COLOR = (220, 120, 60)
EQ_COLOR = (60, 200, 130)
TEXT_COLOR = (235, 235, 240)
HIGHLIGHT = (240, 230, 80)
GAMEOVER_COLOR = (220, 70, 70)

DIGITS = list("0123456789")
OPERATORS = list("+-*%=")

INITIAL_FALL_MS = 600
MIN_FALL_MS = 90
SOFT_DROP_MS = 50


LEVEL_STEP_POINTS = 5000


def score_for_level(level):
    return (level - 1) * LEVEL_STEP_POINTS


def width_for_level(level):
    return max(MIN_WIDTH, MAX_WIDTH - (level - 1))


def make_piece(char):
    if char in DIGITS:
        return {"char": char, "kind": "num"}
    return {"char": char, "kind": "eq" if char == "=" else "op"}


SHAPES = [
    [(0, 0)],                             
    [(0, 0), (0, 1)],                    
    [(0, 0), (0, 1), (0, 2)],              
    [(0, 0), (1, 0), (1, 1)],              
    [(0, 0), (0, 1), (1, 0), (1, 1)],      
    [(0, 0), (0, 1), (0, 2), (0, 3)],     
    [(0, 0), (0, 1), (0, 2), (1, 1)],     
    [(0, 1), (0, 2), (1, 0), (1, 1)],      
    [(0, 0), (0, 1), (1, 1), (1, 2)],      
    [(0, 0), (1, 0), (2, 0), (2, 1)],     
    [(0, 1), (1, 1), (2, 1), (2, 0)],      
]

EQUALS_PER_BAG = 2 

def make_bag(width):
    """A shuffled batch of `width` pieces split evenly between operators and
    digits (operator chance ~50%). Of the operators, up to EQUALS_PER_BAG are
    '=' and the rest are non-'=' operators (+ - * %)."""
    op_count = width // 2
    eq_count = min(EQUALS_PER_BAG, op_count)
    chars = ["="] * eq_count
    chars += [random.choice("+-*%") for _ in range(op_count - eq_count)]
    chars += [random.choice(DIGITS) for _ in range(width - op_count)]
    random.shuffle(chars)
    return [make_piece(c) for c in chars]


SAMPLE_RATE = 44100


def synth_sound(notes, total_ms=None, volume=0.4):
    if pygame.mixer.get_init() is None:
        return None
    if total_ms is None:
        total_ms = max(start + dur for _, start, dur in notes)
    n = max(1, int(SAMPLE_RATE * total_ms / 1000))
    samples = [0.0] * n
    attack = SAMPLE_RATE * 0.004
    for freq, start, dur in notes:
        s0 = int(SAMPLE_RATE * start / 1000)
        cnt = max(1, int(SAMPLE_RATE * dur / 1000))
        for i in range(cnt):
            idx = s0 + i
            if idx >= n:
                break
            env = 1.0 - i / cnt                       
            atk = min(1.0, i / attack) if attack else 1.0
            samples[idx] += math.sin(2 * math.pi * freq * i / SAMPLE_RATE) * env * atk
    buf = array.array("h")
    amp = 32767 * volume
    for v in samples:
        clamped = max(-1.0, min(1.0, v))
        iv = int(amp * clamped)
        buf.append(iv)   
        buf.append(iv)   
    return pygame.mixer.Sound(buffer=buf.tobytes())


def make_music_notes():
    beat = 360 
    lead = [440, 523, 659, 523, 587, 494, 392, 494] 
    bass = [110, 87, 98, 82]                           
    notes = []
    for i, freq in enumerate(lead):
        notes.append((freq, i * beat, beat - 20))
    for i, freq in enumerate(bass):
        notes.append((freq, i * 2 * beat, 2 * beat - 20))
    return notes


class SoundBank:

    def __init__(self):
        self.enabled = pygame.mixer.get_init() is not None
        self.muted = False
        self.sounds = {}
        self.music = None
        self.music_channel = None
        if not self.enabled:
            return
        specs = {
            "move":     ([(330, 0, 25)], 0.18),
            "drop":     ([(440, 0, 40), (220, 35, 70)], 0.30),
            "lock":     ([(150, 0, 90)], 0.35),
            "pair":     ([(700, 0, 50), (1050, 40, 60)], 0.30),
            "numline":  ([(880, 0, 70), (1175, 60, 70), (1568, 120, 90)], 0.32),
            "equation": ([(523, 0, 90), (659, 80, 90), (784, 160, 140)], 0.40),
            "level":    ([(523, 0, 90), (659, 90, 90), (784, 180, 90), (1047, 270, 180)], 0.42),
            "gameover": ([(440, 0, 180), (349, 170, 200), (262, 360, 360)], 0.45),
        }
        for name, (notes, vol) in specs.items():
            try:
                self.sounds[name] = synth_sound(notes, volume=vol)
            except (pygame.error, ValueError):
                self.sounds[name] = None
        try:
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(1)
            self.music_channel = pygame.mixer.Channel(0)
            self.music = synth_sound(make_music_notes(), volume=0.16)
        except (pygame.error, ValueError):
            self.music = None
            self.music_channel = None

    def play(self, name):
        if not self.enabled or self.muted:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def start_music(self):
        if self.music_channel is not None and self.music is not None and not self.muted:
            self.music_channel.play(self.music, loops=-1)

    def stop_music(self):
        if self.music_channel is not None:
            self.music_channel.stop()

    def set_music_paused(self, paused):
        if self.music_channel is None or self.muted:
            return
        if paused:
            self.music_channel.pause()
        else:
            self.music_channel.unpause()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            pygame.mixer.stop() 
        else:
            self.start_music()
        return self.muted


def tokenize(expr):
    tokens = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c.isdigit():
            j = i
            while j < len(expr) and expr[j].isdigit():
                j += 1
            tokens.append(("num", int(expr[i:j])))
            i = j
        elif c in "+-*%":
            tokens.append(("op", c))
            i += 1
        else:
            return None
    return tokens


def evaluate(expr):
    """Evaluate a + - * % expression with non-negative integer operands.
    Returns an int, or None if malformed or divides by zero."""
    if not expr:
        return None
    tokens = tokenize(expr)
    if tokens is None or len(tokens) % 2 == 0:
        return None
    for i, t in enumerate(tokens):
        expected = "num" if i % 2 == 0 else "op"
        if t[0] != expected:
            return None
    nums = [tokens[0][1]]
    later_ops = []
    for i in range(1, len(tokens), 2):
        op = tokens[i][1]
        num = tokens[i + 1][1]
        if op in "*%":
            prev = nums.pop()
            if op == "%" and num == 0:
                return None
            nums.append(prev * num if op == "*" else prev % num)
        else:
            later_ops.append(op)
            nums.append(num)
    result = nums[0]
    for i, op in enumerate(later_ops):
        result = result + nums[i + 1] if op == "+" else result - nums[i + 1]
    return result


class Game:
    def __init__(self):
        setup_logging()
        log.info("starting Calculate Block")
        try:
            pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
        except pygame.error:
            pass
        pygame.init()
        try:
            pygame.mixer.init(SAMPLE_RATE, -16, 2, 512)
        except pygame.error:
            pass
        pygame.display.set_caption("Calculate Block")
        self.font_cell = pygame.font.SysFont("consolas", 22, bold=True)
        self.font_hud = pygame.font.SysFont("consolas", 18, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 36, bold=True)
        self.sound = SoundBank()
        self.clock = pygame.time.Clock()
        self.width = width_for_level(1)
        self._apply_layout()
        self.reset()
        self.sound.start_music()

    def _apply_layout(self):

        self.play_w = self.width * CELL
        self.play_h = GRID_ROWS * CELL
        self.play_x = FRAME
        self.play_y = FRAME
        self.hud_x = self.play_x + self.play_w + FRAME
        self.win_w = self.play_w + HUD_W + FRAME * 3
        self.win_h = self.play_h + FRAME * 2
        self.screen = pygame.display.set_mode((self.win_w, self.win_h))

    def reset(self):
        self.width = width_for_level(1)
        self._apply_layout()
        self.grid = [[None] * self.width for _ in range(GRID_ROWS)]
        self.score = 0
        self.lines = 0
        self.level = 1
        self.fall_ms = INITIAL_FALL_MS
        self.fall_acc = 0
        self.soft_drop = False
        self.piece_bag = []
        self.next_piece = self.make_falling_piece()
        self.game_over = False
        self.paused = False
        self.flash_rows = []
        self.flash_cells = set()
        self.last_message = ""
        self.spawn()

    def draw_piece(self):
        """Pop the next block from the bag, refilling it when empty so each
        `width` blocks are split evenly between operators and digits."""
        if not self.piece_bag:
            self.piece_bag = make_bag(self.width)
        return self.piece_bag.pop()

    def make_falling_piece(self):
        """Build a falling piece: a random 1-4 block shape whose cells each carry
        a character drawn from the bag. Returned as {"cells": [{dr, dc, char,
        kind}, ...]} with offsets relative to the piece's top-left anchor."""
        shape = random.choice(SHAPES)
        cells = []
        for dr, dc in shape:
            block = self.draw_piece()
            cells.append({"dr": dr, "dc": dc, "char": block["char"], "kind": block["kind"]})
        return {"cells": cells}

    def spawn(self):
        self.piece = self.next_piece
        self.next_piece = self.make_falling_piece()
        cells = self.piece["cells"]
        shape_w = 1 + max(c["dc"] for c in cells)
        self.px = max(0, (self.width - shape_w) // 2)
        self.py = 0
        log.debug("spawn %d-block piece chars=%s at px=%d",
                  len(cells), "".join(c["char"] for c in cells), self.px)
        if not self.placement_valid(self.px, self.py, cells):
            self.game_over = True
            self.sound.play("gameover")
            log.info("GAME OVER score=%d level=%d lines=%d", self.score, self.level, self.lines)

    def placement_valid(self, px, py, cells):
        """True if every cell of the piece at (px, py) is in bounds and lands on
        an empty grid square."""
        for c in cells:
            r, col = py + c["dr"], px + c["dc"]
            if col < 0 or col >= self.width or r >= GRID_ROWS:
                return False
            if r >= 0 and self.grid[r][col] is not None:
                return False
        return True

    def can_move(self, dx, dy):
        return self.placement_valid(self.px + dx, self.py + dy, self.piece["cells"])

    def rotate(self):
        """Rotate the piece 90 clockwise about its top-left, re-normalized to
        non-negative offsets, with small wall kicks so it can turn near edges."""
        rotated = [{"dr": c["dc"], "dc": -c["dr"], "char": c["char"], "kind": c["kind"]}
                   for c in self.piece["cells"]]
        min_dr = min(c["dr"] for c in rotated)
        min_dc = min(c["dc"] for c in rotated)
        for c in rotated:
            c["dr"] -= min_dr
            c["dc"] -= min_dc
        for dx in (0, -1, 1, -2, 2):
            if self.placement_valid(self.px + dx, self.py, rotated):
                self.px += dx
                self.piece = {"cells": rotated}
                self.sound.play("move")
                log.debug("rotate piece (kick dx=%d) -> px=%d", dx, self.px)
                return
        log.debug("rotate blocked")

    def lock_piece(self):
        for c in self.piece["cells"]:
            r, col = self.py + c["dr"], self.px + c["dc"]
            if 0 <= r < GRID_ROWS and 0 <= col < self.width:
                self.grid[r][col] = {"char": c["char"], "kind": c["kind"]}
        log.debug("lock piece at px=%d py=%d", self.px, self.py)
        self.sound.play("lock")
        self.clear_rows()
        if not self.game_over:
            self.spawn()

    def clear_rows(self):
        messages = []
        while True:
            eq_message = self.remove_equations()
            if eq_message:
                messages.append(eq_message)
            line_message = self.remove_number_lines()
            if line_message:
                messages.append(line_message)
            pair_message = self.remove_operator_pairs()
            if pair_message:
                messages.append(pair_message)
            if not (eq_message or line_message or pair_message):
                break

        self.last_message = "  |  ".join(messages) if messages else ""

    def _filled_runs(self, r):
        """Yield each maximal run of consecutive filled cells in row `r` as a list
        of (col, char). Gaps (empty cells) separate runs."""
        runs = []
        c = 0
        while c < self.width:
            if self.grid[r][c] is None:
                c += 1
                continue
            run = []
            while c < self.width and self.grid[r][c] is not None:
                run.append((c, self.grid[r][c]["char"]))
                c += 1
            runs.append(run)
        return runs

    def remove_equations(self):
        """When any '='-equation in a row is satisfied (within a contiguous run of
        filled cells; gaps split a row into independent runs), the WHOLE row is
        removed and the rows above drop down. Credit for the row is the sum of all
        its number cells' values."""
        rows_to_clear = []
        credit_total = 0
        parts = []

        for r in range(GRID_ROWS):
            if not self._row_has_equation(r):
                continue
            row_sum = sum(int(self.grid[r][c]["char"]) for c in range(self.width)
                          if self.grid[r][c] is not None and self.grid[r][c]["kind"] == "num")
            rows_to_clear.append(r)
            credit_total += row_sum
            parts.append(f"= row (+{row_sum})")

        if not rows_to_clear:
            return ""

        self.sound.play("equation")
        self.flash_rows = list(rows_to_clear)
        self.draw()
        pygame.display.flip()
        pygame.time.delay(220)
        self.flash_rows = []

        for r in sorted(rows_to_clear):
            del self.grid[r]
            self.grid.insert(0, [None] * self.width)

        self.score += credit_total
        self.lines += len(rows_to_clear)
        log.debug("equation clear: rows=%s credit=%d score=%d", rows_to_clear, credit_total, self.score)

        return "  |  ".join(parts)

    def _row_has_equation(self, r):
        """True if any contiguous run in row `r` contains a satisfied equation,
        i.e. two '='-separated segments on either side of a '=' that evaluate
        equal."""
        for run in self._filled_runs(r):
            chars = [ch for _, ch in run]
            if "=" not in chars:
                continue
            segments = [[]]
            for ch in chars:
                if ch == "=":
                    segments.append([])
                else:
                    segments[-1].append(ch)
            for i in range(len(segments) - 1):
                lv = evaluate("".join(segments[i]))
                rv = evaluate("".join(segments[i + 1]))
                if lv is not None and rv is not None and lv == rv:
                    return True
        return False

    def remove_operator_pairs(self):
        op_chars = ["+","=","/","*"]
        def is_op(orow, ocol):
            cell = self.grid[orow][ocol]
            return cell is not None and cell["char"] in op_chars

        visited = [[False] * self.width for _ in range(GRID_ROWS)]
        removed = set()
        credit = 0
        pair_count = 0
        cluster_count = 0

        for r in range(GRID_ROWS):
            for c in range(self.width):
                if visited[r][c] or not is_op(r, c):
                    continue
                comp = []
                stack = [(r, c)]
                visited[r][c] = True
                while stack:
                    cr, cc = stack.pop()
                    comp.append((cr, cc))
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = cr + dr, cc + dc
                        if (0 <= nr < GRID_ROWS and 0 <= nc < self.width
                                and not visited[nr][nc] and is_op(nr, nc)):
                            visited[nr][nc] = True
                            stack.append((nr, nc))
                if len(comp) < 2:
                    continue
                comp_set = set(comp)
                has_bend = any(
                    ((cr - 1, cc) in comp_set or (cr + 1, cc) in comp_set) and
                    ((cr, cc - 1) in comp_set or (cr, cc + 1) in comp_set)
                    for cr, cc in comp)
                if has_bend:
                    removed.update(comp)
                    credit += len(comp) - 1
                    cluster_count += 1
                else:
                    ordered = sorted(comp)  
                    for i in range(0, len(ordered) - 1, 2):
                        removed.add(ordered[i])
                        removed.add(ordered[i + 1])
                        credit += 1
                        pair_count += 1

        if not removed:
            return ""

        self.sound.play("pair")
        self.flash_cells = set(removed)
        self.draw()
        pygame.display.flip()
        pygame.time.delay(180)
        self.flash_cells = set()

        for r, c in removed:
            self.grid[r][c] = None

        self.apply_gravity()

        self.score += credit
        log.debug("operator clear: pairs=%d clusters=%d cells=%d credit=%d score=%d",
                  pair_count, cluster_count, len(removed), credit, self.score)
        bits = []
        if pair_count:
            bits.append(f"op pairs x{pair_count}")
        if cluster_count:
            bits.append(f"op clusters x{cluster_count}")
        return f"{' '.join(bits)} (+{credit})"

    def remove_number_lines(self):
        """Any straight run of 3 number cells (horizontal, vertical, or either
        diagonal) whose digits are all identical OR form 3 consecutive integers
        (ascending or descending) is removed; blocks above fall down to fill the
        gaps. Credit = (sum of the removed digits) + 100."""
        directions = ((0, 1), (1, 0), (1, 1), (1, -1))
        to_remove = set()

        def digit_at(rr, cc):
            cell = self.grid[rr][cc]
            if cell is not None and cell["kind"] == "num":
                return int(cell["char"])
            return None

        for r in range(GRID_ROWS):
            for c in range(self.width):
                for dr, dc in directions:
                    cells = []
                    vals = []
                    for k in range(3):
                        nr, nc = r + dr * k, c + dc * k
                        if not (0 <= nr < GRID_ROWS and 0 <= nc < self.width):
                            break
                        v = digit_at(nr, nc)
                        if v is None:
                            break
                        cells.append((nr, nc))
                        vals.append(v)
                    if len(vals) < 3:
                        continue
                    same = all(v == vals[0] for v in vals)
                    asc = all(vals[i + 1] - vals[i] == 1 for i in range(2))
                    desc = all(vals[i + 1] - vals[i] == -1 for i in range(2))
                    if same or asc or desc:
                        to_remove.update(cells)

        if not to_remove:
            return ""

        self.sound.play("numline")
        self.flash_cells = set(to_remove)
        self.draw()
        pygame.display.flip()
        pygame.time.delay(180)
        self.flash_cells = set()

        credit = 0
        for r, c in to_remove:
            credit += int(self.grid[r][c]["char"])
            self.grid[r][c] = None
        credit += 100

        self.apply_gravity()

        self.score += credit
        log.debug("number-line clear: cells=%d credit=%d score=%d", len(to_remove), credit, self.score)
        return f"4-line x{len(to_remove)} (+{credit})"

    def apply_gravity(self):
        """Drop every block straight down within its column to fill empty gaps."""
        for c in range(self.width):
            stack = [self.grid[r][c] for r in range(GRID_ROWS) if self.grid[r][c] is not None]
            empty = GRID_ROWS - len(stack)
            for r in range(GRID_ROWS):
                self.grid[r][c] = stack[r - empty] if r >= empty else None

    def maybe_level_up(self):
        if self.game_over or self.paused:
            return
        while self.score >= score_for_level(self.level + 1):
            self.level_up()

    def level_up(self):
        bonus = sum(int(cell["char"]) for row in self.grid for cell in row
                    if cell is not None and cell["kind"] == "num")

        filled = [(r, c) for r in range(GRID_ROWS) for c in range(self.width)
                  if self.grid[r][c] is not None]
        if filled:
            self.flash_cells = set(filled)
            self.draw()
            pygame.display.flip()
            pygame.time.delay(220)
            self.flash_cells = set()

        self.score += bonus
        self.level += 1
        self.fall_ms = max(MIN_FALL_MS, int(INITIAL_FALL_MS * (0.85 ** (self.level - 1))))
        self.width = width_for_level(self.level)
        self._apply_layout()
        self.grid = [[None] * self.width for _ in range(GRID_ROWS)]
        self.piece_bag = []
        self.last_message = f"LEVEL {self.level}!  numbers banked (+{bonus})"
        self.sound.play("level")
        log.info("LEVEL UP -> %d  width=%d  banked=%d  score=%d",
                 self.level, self.width, bonus, self.score)
        self.spawn()

    def step(self, dt):
        if self.game_over or self.paused:
            return
        self.fall_acc += dt
        interval = SOFT_DROP_MS if self.soft_drop else self.fall_ms
        while self.fall_acc >= interval:
            self.fall_acc -= interval
            if self.can_move(0, 1):
                self.py += 1
            else:
                self.lock_piece()
                return

    def hard_drop(self):
        if self.game_over or self.paused:
            return
        self.sound.play("drop")
        while self.can_move(0, 1):
            self.py += 1
            self.score += 1
        self.lock_piece()

    def handle_key(self, key):
        if key == pygame.K_m:
            self.sound.toggle_mute()
            return
        if self.game_over:
            if key == pygame.K_r:
                self.reset()
            return
        if key == pygame.K_p:
            self.paused = not self.paused
            self.sound.set_music_paused(self.paused)
            return
        if self.paused:
            return
        if key == pygame.K_LEFT and self.can_move(-1, 0):
            self.px -= 1
            self.sound.play("move")
        elif key == pygame.K_RIGHT and self.can_move(1, 0):
            self.px += 1
            self.sound.play("move")
        elif key == pygame.K_DOWN:
            self.soft_drop = True
        elif key == pygame.K_UP:
            self.rotate()
        elif key == pygame.K_SPACE:
            self.hard_drop()

    def handle_key_up(self, key):
        if key == pygame.K_DOWN:
            self.soft_drop = False

    def block_color(self, piece):
        kind = piece.get("kind", "num")
        if kind == "num":
            return NUM_COLOR
        if kind == "eq":
            return EQ_COLOR
        return OP_COLOR

    def draw_block(self, x, y, piece, flash=False):
        color = HIGHLIGHT if flash else self.block_color(piece)
        rect = pygame.Rect(x + 1, y + 1, CELL - 2, CELL - 2)
        pygame.draw.rect(self.screen, color, rect, border_radius=4)
        text = self.font_cell.render(piece["char"], True, (15, 15, 20) if flash else TEXT_COLOR)
        text_rect = text.get_rect(center=(x + CELL // 2, y + CELL // 2))
        self.screen.blit(text, text_rect)

    def draw(self):
        self.screen.fill(BG)
        pygame.draw.rect(
            self.screen, FRAME_COLOR,
            (self.play_x - FRAME // 2, self.play_y - FRAME // 2,
             self.play_w + FRAME, self.play_h + FRAME),
            width=FRAME // 2,
        )
        play_rect = pygame.Rect(self.play_x, self.play_y, self.play_w, self.play_h)
        pygame.draw.rect(self.screen, (10, 10, 14), play_rect)
        for c in range(self.width + 1):
            x = self.play_x + c * CELL
            pygame.draw.line(self.screen, GRID_LINE, (x, self.play_y), (x, self.play_y + self.play_h))
        for r in range(GRID_ROWS + 1):
            y = self.play_y + r * CELL
            pygame.draw.line(self.screen, GRID_LINE, (self.play_x, y), (self.play_x + self.play_w, y))

        for r in range(GRID_ROWS):
            for c in range(self.width):
                cell = self.grid[r][c]
                if cell is not None:
                    is_flash = r in self.flash_rows or (r, c) in self.flash_cells
                    self.draw_block(self.play_x + c * CELL, self.play_y + r * CELL, cell,
                                    flash=is_flash)

        if not self.game_over:
            for c in self.piece["cells"]:
                r, col = self.py + c["dr"], self.px + c["dc"]
                if r >= 0:
                    self.draw_block(self.play_x + col * CELL, self.play_y + r * CELL, c)

        self.draw_hud()

        if self.paused:
            self.draw_centered_overlay("PAUSED", "Press P to resume", TEXT_COLOR)
        elif self.game_over:
            self.draw_centered_overlay("GAME OVER", "Press R to restart", GAMEOVER_COLOR)

    def draw_hud(self):
        x = self.hud_x
        y = self.play_y
        rows = [
            ("SCORE", str(self.score)),
            ("LINES", str(self.lines)),
            ("LEVEL", str(self.level)),
            ("WIDTH", str(self.width)),
        ]
        for label, value in rows:
            self.screen.blit(self.font_hud.render(label, True, FRAME_COLOR), (x, y))
            y += 22
            self.screen.blit(self.font_hud.render(value, True, TEXT_COLOR), (x, y))
            y += 26

        y += 10
        self.screen.blit(self.font_hud.render("NEXT", True, FRAME_COLOR), (x, y))
        y += 24
        ncells = self.next_piece["cells"]
        shape_w = (1 + max(c["dc"] for c in ncells)) * CELL
        shape_h = (1 + max(c["dr"] for c in ncells)) * CELL
        preview_x = x + (HUD_W - FRAME - shape_w) // 2
        for c in ncells:
            self.draw_block(preview_x + c["dc"] * CELL, y + c["dr"] * CELL, c)

        y += shape_h + 20
        self.screen.blit(self.font_hud.render("CONTROLS", True, FRAME_COLOR), (x, y))
        y += 22
        for line in ("Left/Right move", "Up rotate", "Down soft drop", "Space hard drop",
                     "P pause", "M mute", "R restart"):
            self.screen.blit(self.font_hud.render(line, True, TEXT_COLOR), (x, y))
            y += 20

        y += 6
        self.screen.blit(self.font_hud.render("TIPS", True, FRAME_COLOR), (x, y))
        y += 22
        for line in ("= row: L==R clears", "credit = |value|", "no '=': no clear",
                     "2 ops adj: vanish +1", "4 same/seq nums: clear"):
            self.screen.blit(self.font_hud.render(line, True, TEXT_COLOR), (x, y))
            y += 20

        if self.last_message:
            msg_surface = self.font_hud.render(self.last_message, True, HIGHLIGHT)
            self.screen.blit(msg_surface, (self.play_x, self.play_y + self.play_h + 2))

    def draw_centered_overlay(self, title, subtitle, color):
        overlay = pygame.Surface((self.play_w, self.play_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (self.play_x, self.play_y))
        title_surf = self.font_big.render(title, True, color)
        sub_surf = self.font_hud.render(subtitle, True, TEXT_COLOR)
        self.screen.blit(title_surf, title_surf.get_rect(
            center=(self.play_x + self.play_w // 2, self.play_y + self.play_h // 2 - 16)))
        self.screen.blit(sub_surf, sub_surf.get_rect(
            center=(self.play_x + self.play_w // 2, self.play_y + self.play_h // 2 + 24)))

    async def run(self):
        while True:
            dt = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)
                if event.type == pygame.KEYUP:
                    self.handle_key_up(event.key)
            self.step(dt)
            self.maybe_level_up()
            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(Game().run())