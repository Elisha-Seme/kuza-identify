"""Builds the Kuza item bank + question pictures.

Run from the repo root:   python3 tools/item-bank/build.py
Needs:                    pip install cairosvg   (for the PNG copies WhatsApp needs)

Writes:
  backend/app/services/adaptive_item_engine/item_bank.json   (full bank, server only)
  dashboard/public/items/bank.json                          (public copy: no answers/scorer notes)
  dashboard/public/items/svg/*.svg, png/*.png               (pictures, served by the dashboard)

Edit the items/pictures here, re-run, commit the outputs. Don't hand-edit the JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from draw import *  # noqa: E402,F401,F403

ROOT = Path(__file__).resolve().parent.parent.parent
BANK_PATH = ROOT / "backend" / "app" / "services" / "adaptive_item_engine" / "item_bank.json"
PUBLIC = ROOT / "dashboard" / "public" / "items"
SVG_DIR = PUBLIC / "svg"
PNG_DIR = PUBLIC / "png"
SVG_DIR.mkdir(parents=True, exist_ok=True)
PNG_DIR.mkdir(parents=True, exist_ok=True)

IMAGES: dict[str, str] = {}


def img(name: str, body: str, title: str = "") -> str:
    IMAGES[name] = svg(body, title=title)
    return f"svg/{name}.svg"


def letters_row(objs, y=200, labels="ABCD", spacing=None, start=None, ly=None):
    n = len(objs)
    spacing = spacing or 560 / n
    start = start or (320 - spacing * (n - 1) / 2)
    out = ""
    for i, o in enumerate(objs):
        x = start + i * spacing
        out += g(o, x, y)
        if labels:
            out += option_label(x, ly or (y + 80), labels[i])
    return out


# =============================================================== IMAGES
# --- numerical
b = ""
for i, x in enumerate([130, 320, 510]):
    b += g(basket(), x, 250)
    for j, dx in enumerate([-24, 24, -12, 14]):
        b += g(mango(), x + dx, 220 - (j // 2) * 34, 0.7)
b += g(mango(), 250, 345, 0.7) + g(mango(), 390, 345, 0.7, 30)
num_p1 = img("num-p1", b, "Three baskets of mangoes and two loose mangoes")

b = ""
for x, v in zip([90, 180, 270, 350, 420], [20, 10, 10, 5, 1]):
    b += g(coin(v, 38 if v >= 10 else 30), x, 200)
b += rect(480, 120, 130, 160, "#FFFFFF", rx=16)
b += g(path("M -40 10 C -40 -30 40 -30 40 10 Z", fill=TAN), 545, 200)  # mandazi
b += rect(495, 240, 100, 32, YEL, rx=8, sw=3) + text(545, 257, "KSh 40", 20)
num_p2 = img("num-p2", b, "Coins worth 20, 10, 10, 5 and 1 shilling, and a mandazi priced 40 shillings")

b = ""
for r in range(3):
    for c in range(4):
        b += g(orange_fruit(), 90 + c * 72, 120 + r * 80, 0.85)
b += rect(400, 90, 200, 70, "#FFFFFF", rx=12) + text(500, 112, "12 = KSh 60", 24) + text(500, 142, "buy / nunua", 18, TEAL, weight="normal")
b += rect(400, 230, 200, 70, "#FFFFFF", rx=12) + text(500, 252, "1 = KSh 8", 24) + text(500, 282, "sell / uza", 18, TEAL, weight="normal")
num_p3 = img("num-p3", b, "Twelve oranges bought for 60 shillings, each sold for 8 shillings")

b = line(80, 330, 600, 330) + line(80, 330, 80, 60)
for i, (d, v) in enumerate(zip(["Mon", "Tue", "Wed", "Thu", "Fri"], [10, 15, 20, 25, None])):
    x = 120 + i * 100
    if v is None:
        b += rect(x, 330 - 30 * 8, 60, 30 * 8, "none", rx=4, sw=3).replace('stroke-width="3"', 'stroke-width="3" stroke-dasharray="10 8"')
        b += text(x + 30, 330 - 30 * 8 - 24, "?", 34, ORA)
    else:
        b += rect(x, 330 - v * 8, 60, v * 8, TEAL_L, rx=4)
        b += text(x + 30, 330 - v * 8 - 20, v, 24)
    b += text(x + 30, 358, d, 20, weight="normal")
num_p4 = img("num-p4", b, "Bar chart of matatu passengers: Monday 10, Tuesday 15, Wednesday 20, Thursday 25, Friday unknown")


def scale(left, right, tilt=0):
    s = poly([(300, 330), (340, 330), (320, 200)], GREY) + line(140, 200 + tilt, 500, 200 - tilt, sw=6)
    s += path(f"M 110 {205+tilt} L 210 {205+tilt} L 190 {245+tilt} L 130 {245+tilt} Z", fill="#FFFFFF")
    s += path(f"M 430 {205-tilt} L 530 {205-tilt} L 510 {245-tilt} L 450 {245-tilt} Z", fill="#FFFFFF")
    return s + left + right


lm = g(mango(), 140, 165, 0.75) + g(mango(), 185, 165, 0.75)
rb = "".join(g(banana(), 450 + (i % 3) * 32, 175 - (i // 3) * 26, 0.55) for i in range(6))
b = scale(lm, rb) + text(320, 60, "=", 40) + text(160, 300, "2", 30) + text(480, 300, "6", 30)
num_p5 = img("num-p5", b, "A balance: two mangoes on one side balance six bananas on the other")

b = ""
for i in range(3):
    b += g(chapati(46), 130 + i * 120, 130)
for i in range(4):
    b += g(child([TEAL, ORA, BLUE, GRN][i]), 110 + i * 140, 300, 0.9)
num_p6 = img("num-p6", b, "Three chapatis above four children")

# --- verbal
b = letters_row([mango(), orange_fruit(), ball(), banana()], y=180)
vrb_p1 = img("vrb-p1", b, "Four pictures: A mango, B orange, C ball, D banana")

order = [2, 0, 3, 1]  # A..D show stages 2,0,3,1 -> correct order B, D, A, C
b = "".join(g(stage(s), 95 + i * 150, 210, 1.15) + option_label(95 + i * 150, 330, "ABCD"[i]) for i, s in enumerate(order))
vrb_p3 = img("vrb-p3", b, "Four mixed-up pictures of a maize plant growing: A young plant, B seed in soil, C tall maize with a cob, D small sprout")

b = g(cup(), 320, 250, 2.6)
for i, (x, y) in enumerate([(320, 70), (320, 115), (305, 150)]):
    b += g(path("M 0 -14 C 8 -2 10 6 0 12 C -10 6 -8 -2 0 -14 Z", fill=BLUE, sw=3), x, y)
vrb_p4 = img("vrb-p4", b, "A cup slowly filling with drops of water")

b = (g(house().replace('fill="#FDE68A"', 'fill="#FDE68A"'), 320, 230, 4.0)
     .replace(rect(-7, 10, 14, 20, BRN, rx=2, sw=3), ""))
b += text(500, 110, "?", 70, ORA)
vrb_p5 = img("vrb-p5", b, "A little house with no door")

# --- pattern
seq = [("circle", RED), ("square", BLUE)] * 3
b = line(50, 150, 590, 150, stroke=BRN, sw=3)
for i, (k, c) in enumerate(seq[:5]):
    b += g(shape(k, 26, c), 80 + i * 95, 150)
b += circle(80 + 5 * 95, 150, 30, "none", sw=3).replace('fill="none"', 'fill="none" stroke-dasharray="8 6"') + text(80 + 5 * 95, 152, "?", 30, ORA)
opts = [shape("circle", 24, RED), shape("square", 24, BLUE), shape("triangle", 24, YEL), shape("square", 24, RED)]
b += letters_row(opts, y=280, ly=345, spacing=120)
pat_p1 = img("pat-p1", b, "Bead pattern: red circle, blue square, red circle, blue square, red circle, then a gap. Options: A red circle, B blue square, C yellow triangle, D red square")


def sticks(n, x0, y0, u=40):
    s = ""
    for i in range(n + 1):
        s += line(x0 + i * u, y0, x0 + i * u, y0 + u, stroke=BRN, sw=7)
    for i in range(n):
        s += line(x0 + i * u, y0, x0 + (i + 1) * u, y0, stroke=BRN, sw=7)
        s += line(x0 + i * u, y0 + u, x0 + (i + 1) * u, y0 + u, stroke=BRN, sw=7)
    return s


b = sticks(1, 60, 140) + sticks(2, 160, 140) + sticks(3, 300, 140)
b += text(80, 230, "4", 30) + text(200, 230, "7", 30) + text(360, 230, "10", 30)
b += rect(490, 120, 110, 120, "none", rx=10, sw=3).replace('fill="none"', 'fill="none" stroke-dasharray="10 8"') + text(545, 180, "?", 44, ORA)
b += text(320, 320, "1 → 2 → 3 → 4", 26, TEAL)
pat_p2 = img("pat-p2", b, "Squares made of sticks: 1 square uses 4 sticks, 2 squares use 7, 3 squares use 10. How many for 4 squares?")


def dots(cols, rows, x0, y0, d=13):
    return "".join(circle(x0 + c * d, y0 + r * d, 4.5, TEAL, stroke="none") for r in range(rows) for c in range(cols))


b = ""
for i, (c, r) in enumerate([(2, 1), (3, 2), (4, 3), (5, 4)]):
    x = 70 + i * 120
    b += dots(c, r, x, 130)
    b += text(x + (c - 1) * 6.5, 250, [2, 6, 12, 20][i], 30)
b += text(560, 160, "30", 30) + text(560, 250, "?", 40, ORA)
b += text(320, 330, "2, 6, 12, 20, 30, ?", 30, TEAL)
pat_p3 = img("pat-p3", b, "Dot rectangles: 1 by 2 is 2 dots, 2 by 3 is 6, 3 by 4 is 12, 4 by 5 is 20, then 30, then what?")

# 3x3 matrix: rows=shape, cols=count
kinds = ["circle", "square", "triangle"]
fills = [TEAL_L, YEL, ORA]
b = ""
for r in range(3):
    for c in range(3):
        x, y = 50 + c * 100, 40 + r * 105
        b += rect(x, y, 90, 95, "#FFFFFF", rx=10, sw=3)
        if r == 2 and c == 2:
            b += text(x + 45, y + 48, "?", 44, ORA)
            continue
        n = c + 1
        for k in range(n):
            b += g(shape(kinds[r], 11, fills[r]), x + 45 + (k - (n - 1) / 2) * 26, y + 48)
choices = [("triangle", 2), ("square", 3), ("triangle", 3), ("circle", 3)]
for i, (kd, n) in enumerate(choices):
    x, y = 400 + (i % 2) * 110, 60 + (i // 2) * 160
    b += rect(x, y, 95, 95, "#FFFFFF", rx=10, sw=3)
    for k in range(n):
        b += g(shape(kd, 11, fills[kinds.index(kd)]), x + 47 + (k - (n - 1) / 2) * 26, y + 48)
    b += option_label(x + 47, y + 122, "ABCD"[i])
pat_p4 = img("pat-p4", b, "A 3 by 3 grid: rows are circles, squares, triangles; columns show 1, 2, 3 shapes; bottom-right is missing. Options: A two triangles, B three squares, C three triangles, D three circles")

b = ""
for i, r in enumerate([0, 90, 180]):
    b += rect(40 + i * 140, 50, 110, 110, "#FFFFFF", rx=12, sw=3) + g(arrow(r), 95 + i * 140, 105)
b += rect(460, 50, 110, 110, "none", rx=12, sw=3).replace('fill="none"', 'fill="none" stroke-dasharray="10 8"') + text(515, 107, "?", 44, ORA)
b += letters_row([arrow(0), arrow(270), arrow(90), arrow(180)], y=260, ly=340, spacing=130)
pat_p5 = img("pat-p5", b, "An arrow turns a quarter turn clockwise each step: right, down, left, then what? Options: A right, B up, C down, D left")

b = ""
blocks = [["s", "s", "m"], ["m", "m", "s"], ["s", "s", "m"], ["m", "m", "s"]]
for bi, blk in enumerate(blocks):
    x0 = 22 + bi * 152
    b += rect(x0, 60, 140, 90, "#FFFFFF", rx=12, sw=3)
    for k, sym in enumerate(blk):
        b += g(sun(16) if sym == "s" else moon(), x0 + 28 + k * 42, 105, 0.68 if sym == "s" else 1.0)
b += rect(230, 220, 180, 90, "none", rx=12, sw=3).replace('fill="none"', 'fill="none" stroke-dasharray="10 8"') + text(320, 266, "? ? ?", 40, ORA)
pat_p6 = img("pat-p6", b, "Sun sun moon, moon moon sun, sun sun moon, moon moon sun, then three blanks")

# --- logical
b = ""
for i, (nm, c) in enumerate([("Amani", TEAL), ("Baraka", ORA), ("Chebet", BLUE)]):
    x = 140 + i * 180
    b += g(child(c), x, 260, 1.4) + rect(x - 60, 340, 120, 36, "#FFFFFF", rx=10, sw=3) + text(x, 359, nm, 20)
    b += text(x, 120, "?", 40, ORA)
b += rect(30, 150, 580, 120, "#E2E8F0", rx=14, sw=3)  # curtain hides heights
b += text(320, 210, "curtain / pazia", 22, GREY, weight="normal")
log_p1 = img("log-p1", b, "Three children, Amani, Baraka and Chebet, standing behind a curtain so you cannot see who is tallest")

nodes = {"Home": (90, 300), "Market": (250, 120), "Church": (230, 330), "Clinic": (420, 280), "School": (560, 110)}
edges = [("Home", "Market"), ("Market", "School"), ("Home", "Church"), ("Church", "Clinic"), ("Clinic", "School"), ("Market", "Clinic")]
b = ""
for a, c in edges:
    (x1, y1), (x2, y2) = nodes[a], nodes[c]
    b += line(x1, y1, x2, y2, stroke=GREY, sw=10)
mx, my = (nodes["Market"][0] + nodes["School"][0]) / 2, (nodes["Market"][1] + nodes["School"][1]) / 2
b += line(mx - 18, my - 18, mx + 18, my + 18, stroke=RED, sw=8) + line(mx - 18, my + 18, mx + 18, my - 18, stroke=RED, sw=8)
icons = {"Home": house(), "Market": mango(), "Church": star(22, "#FFFFFF"), "Clinic": rect(-14, -5, 28, 10, RED, rx=2, sw=0) + rect(-5, -14, 10, 28, RED, rx=2, sw=0), "School": g(key(), 0, 0, 0.0)}
for nm, (x, y) in nodes.items():
    b += circle(x, y, 34, "#FFFFFF", sw=4)
    inner = {"School": g(text(0, 2, "ABC", 18, TEAL), 0, 0)}.get(nm) or g(icons[nm], 0, 0, 0.6)
    b += g(inner, x, y) + text(x, y + 52, nm, 20)
log_p2 = img("log-p2", b, "Map with roads between Home, Market, Church, Clinic and School. The road from Market to School is closed (red X)")

b = rect(120, 250, 400, 30, "#B45309", rx=8) + line(150, 280, 150, 340, sw=8) + line(490, 280, 490, 340, sw=8)
for i, lab in enumerate(["LEFT", "MIDDLE", "RIGHT"]):
    x = 187 + i * 133
    b += rect(x - 50, 196, 100, 44, "#FFFFFF", rx=10, sw=3).replace('fill="#FFFFFF"', 'fill="#FFFFFF" stroke-dasharray="8 6"') + text(x, 219, "?", 26, ORA)
    b += text(x, 362, lab, 18, GREY)
for i, (nm, c) in enumerate([("Wanjiru", TEAL), ("Otieno", ORA), ("Fatuma", BLUE)]):
    x = 140 + i * 180
    b += g(child(c), x, 100, 0.8) + rect(x - 55, 148, 110, 32, "#FFFFFF", rx=8, sw=3) + text(x, 165, nm, 18)
log_p4 = img("log-p4", b, "A bench with three empty seats (left, middle, right) and three children: Wanjiru, Otieno, Fatuma")

# --- working memory
show = [mango(), key(), fish(), star()]
b = letters_row(show, y=200, labels="")
b += text(320, 340, "look / tazama", 22, TEAL, weight="normal")
wmm_p1_show = img("wmm-p1-show", b, "Four things: a mango, a key, a fish, a star")
ask = [mango(), cup(), fish(), star()]
b = letters_row(ask, y=180)
wmm_p1_ask = img("wmm-p1-ask", b, "Four things: A mango, B cup, C fish, D star")


def chair():
    return rect(-22, -6, 44, 10, BRN, rx=2, sw=3) + line(-18, 4, -18, 34, sw=5) + line(18, 4, 18, 34, sw=5) + line(18, -6, 18, -40, sw=5) + line(-18, -6, -18, -40, sw=5) + line(-18, -36, 18, -36, sw=5)


def river():
    return path("M -40 -10 C -20 -24 0 4 20 -10 C 30 -18 36 -14 40 -10", stroke=BLUE, sw=8) + path("M -40 12 C -20 -2 0 26 20 12 C 30 4 36 8 40 12", stroke=BLUE, sw=8)


b = letters_row([mango(), chair(), river(), g(text(0, 0, "7", 64), 0, 0), circle(0, 0, 30, BLUE)], y=190, labels="", spacing=115)
wmm_p2_show = img("wmm-p2-show", b, "Five things in a row: mango, chair, river, seven, blue")


def grid(path_cells, numbered=True):
    s = ""
    for r in range(4):
        for c in range(4):
            s += rect(160 + c * 80, 40 + r * 80, 76, 76, "#FFFFFF", rx=8, sw=3)
    for i, (c, r) in enumerate(path_cells):
        x, y = 160 + c * 80 + 38, 40 + r * 80 + 38
        s += circle(x, y, 26, YEL if i else GRN, sw=3)
        if numbered:
            s += text(x, y + 1, i + 1, 22)
    return s


PATH = [(0, 3), (0, 2), (1, 2), (2, 2), (2, 1), (3, 1)]
wmm_p3_show = img("wmm-p3-show", grid(PATH), "A 4 by 4 grid with a numbered path: start bottom-left, up, right, right, up, right")
wmm_p3_ask = img("wmm-p3-ask", grid(PATH[:1], numbered=False) + text(160 + 38, 40 + 3 * 80 + 38, "1", 22), "Empty 4 by 4 grid with only the start square marked")

# --- creativity
bucket = path("M -60 -50 L 60 -50 L 44 60 L -44 60 Z", fill=TEAL_L) + path("M -60 -50 C -60 -120 60 -120 60 -50", sw=5) + line(-52, -30, 52, -30, sw=3)
cre_p1 = img("cre-p1", g(bucket, 320, 220, 1.3) + text(520, 110, "?", 70, ORA), "An empty plastic bucket")
sq = rect(150, 50, 340, 300, "#FFFFFF", rx=6, sw=3) + path("M 240 250 C 220 160 300 120 340 170 C 370 210 330 240 360 260 C 390 280 420 230 400 200", sw=6)
cre_p2 = img("cre-p2", sq + g(text(0, 0, "✎", 40, TEAL), 545, 320), "A sheet of paper with one curvy squiggle line on it")
cloud = path("M 220 160 C 180 160 180 100 230 100 C 240 60 320 50 340 90 C 380 60 440 90 420 130 C 460 140 450 180 410 180 L 230 180 C 225 180 222 170 220 160 Z", fill="#FFFFFF")
drops = "".join(g(path("M 0 -14 C 8 -2 10 6 0 12 C -10 6 -8 -2 0 -14 Z", fill="#FFFFFF", sw=3), x, y) for x, y in [(250, 230), (300, 260), (350, 220), (400, 250), (280, 320), (370, 310)])
cre_p3 = img("cre-p3", cloud + drops + g(house(), 520, 330, 1.2), "A cloud raining white drops of milk over a house")
hill = path("M 20 380 C 200 380 260 120 420 110 C 520 105 600 160 620 160 L 620 380 Z", fill="#86EFAC")
cre_p4 = img("cre-p4", hill + g(child(ORA), 150, 300, 0.9) + g(jerrycan(), 200, 330, 0.8) + g(house(), 460, 80, 1.1) + text(320, 60, "?", 60, ORA),
             "A child with a heavy jerrycan at the bottom of a steep hill, home is at the top")

# --- interests
icons8 = [g(text(0, 0, "123", 34, TEAL), 0, 0), rect(-28, -22, 56, 44, BLUE, rx=4) + line(0, -22, 0, 22, stroke="#FFFFFF", sw=3),
          g(path("M -26 26 L 18 -18 L 26 -10 L -18 34 Z", fill=YEL) + poly([(-26, 26), (-18, 34), (-30, 38)], INK, sw=2), 0, -4),
          rect(-30, 0, 28, 28, ORA, rx=3) + rect(2, 0, 28, 28, TEAL_L, rx=3) + rect(-14, -28, 28, 28, YEL, rx=3),
          rect(-24, -20, 48, 46, BRN, rx=10) + path("M -24 -20 C -10 -30 10 -30 24 -20", fill="#FDE68A") + line(30, -40, 10, -18, sw=4),
          g(tree(), 0, 0, 0.9), ball(), g(path("M -26 22 L 8 -12 M 8 -12 C 2 -26 18 -38 28 -30 L 18 -20 L 24 -14 L 34 -24 C 42 -14 30 2 16 -4", sw=7), 0, 4)]
b = ""
for i, ic in enumerate(icons8):
    x, y = 90 + (i % 4) * 153, 120 + (i // 4) * 160
    b += circle(x, y, 52, "#FFFFFF", sw=3) + g(ic, x, y) + option_label(x + 42, y + 44, "ABCDEFGH"[i])
int_p1 = img("int-p1", b, "Eight pictures: A numbers, B a book, C a pencil, D building blocks, E a drum, F a tree, G a ball, H a spanner")


# =============================================================== ITEMS
def T(en, sw):
    return {"en": en, "sw": sw}


ALL_DELIVERY = ["web_play", "whatsapp_image", "whatsapp_voice", "ivr_voice", "sms_text", "ussd_text", "facilitator_cards"]
PIC_DELIVERY = ["web_play", "whatsapp_image", "whatsapp_voice", "facilitator_cards"]

items = []


def add(**kw):
    kw.setdefault("tier", "pool")
    kw.setdefault("response_modes", ["tap", "type", "voice"])
    kw.setdefault("hints", [])
    items.append(kw)


# ------------------------------------------------------------ numerical
add(id="num-p1", domain="numerical_reasoning", difficulty=1, type="choice",
    prompt=T("Kuza found 3 baskets with 4 mangoes in each, and 2 more mangoes on the ground. How many mangoes are there altogether?",
             "Kuza alipata vikapu 3, kila kimoja kina maembe 4, na maembe mengine 2 chini. Kuna maembe mangapi kwa jumla?"),
    image=num_p1, choices=[T("12", "12"), T("14", "14"), T("16", "16"), T("10", "10")], answer="b",
    text_fallback=T("3 baskets x 4 mangoes, plus 2 more. How many? 1) 12 2) 14 3) 16 4) 10",
                    "Vikapu 3 x maembe 4, ongeza 2. Mangapi? 1) 12 2) 14 3) 16 4) 10"),
    hints=[T("Count one basket first.", "Hesabu kikapu kimoja kwanza."), T("4 + 4 + 4 is 12. Now add the 2 on the ground.", "4 + 4 + 4 ni 12. Sasa ongeza 2 zilizo chini.")],
    delivery=ALL_DELIVERY,
    expected_reasoning="Answer 14 (3x4=12, +2). Warm-up item. Note strategy if explained: counting all vs. grouping by basket (multiplicative thinking is the stronger signal). Image: 3 baskets of 4 mangoes and 2 loose mangoes.")

add(id="num-p2", domain="numerical_reasoning", difficulty=2, type="open_ended", tier="core",
    prompt=T("Kuza has these coins: 20, 10, 10, 5 and 1 shilling. A mandazi costs 40 shillings. Can Kuza buy it? How much money is left after?",
             "Kuza ana sarafu hizi: shilingi 20, 10, 10, 5 na 1. Mandazi linauzwa shilingi 40. Je, Kuza anaweza kulinunua? Atabaki na pesa ngapi?"),
    image=num_p2, response_modes=["type", "voice", "tap"],
    text_fallback=T("Coins: 20, 10, 10, 5, 1. Mandazi costs 40. Can you buy it? How much is left?",
                    "Sarafu: 20, 10, 10, 5, 1. Mandazi ni 40. Unaweza kununua? Utabaki na ngapi?"),
    hints=[T("Add up all the coins first.", "Jumlisha sarafu zote kwanza."), T("The coins make 46 shillings. What is 46 take away 40?", "Sarafu ni shilingi 46. 46 toa 40 ni ngapi?")],
    delivery=ALL_DELIVERY,
    expected_reasoning="Total 20+10+10+5+1=46, so yes; change 6. Credit 'yes' with any correct total. Real-life money context common in Kibera/Mukuru; strong answers may mention which coins to hand over (e.g. 20+10+10 exactly, keep 6), which shows flexible decomposition.")

add(id="num-p3", domain="numerical_reasoning", difficulty=3, type="open_ended",
    prompt=T("A shopkeeper buys 12 oranges for 60 shillings and sells them for 8 shillings each. How much profit does she make? Tell us how you worked it out.",
             "Mwuzaji ananunua machungwa 12 kwa shilingi 60 na anauza kila moja kwa shilingi 8. Anapata faida kiasi gani? Tueleze ulivyofikia jibu."),
    image=num_p3, replaces="num-01", response_modes=["type", "voice"],
    text_fallback=T("Buys 12 oranges for 60 bob, sells each for 8 bob. Profit?", "Ananunua machungwa 12 kwa bob 60, anauza kila moja bob 8. Faida?"),
    hints=[T("How much money does she get if she sells all 12?", "Atapata pesa ngapi akiuza yote 12?"), T("12 x 8 = 96. Now take away what she paid.", "12 x 8 = 96. Sasa toa alicholipa.")],
    delivery=ALL_DELIVERY,
    expected_reasoning="Cost 60, revenue 12x8=96, profit 36. Credit correct method even if arithmetic slips; note per-unit reasoning (cost 5 each, profit 3 each, x12=36) as a more elegant route.")

add(id="num-p4", domain="numerical_reasoning", difficulty=3, type="choice",
    prompt=T("This chart shows how many people rode Kuza's matatu each day. If the pattern carries on, how many will ride on Friday?",
             "Chati hii inaonyesha watu wangapi walipanda matatu ya Kuza kila siku. Mpangilio ukiendelea, watu wangapi watapanda Ijumaa?"),
    image=num_p4, choices=[T("25", "25"), T("28", "28"), T("30", "30"), T("35", "35")], answer="c",
    text_fallback=T("Matatu riders: Mon 10, Tue 15, Wed 20, Thu 25. Friday? 1) 25 2) 28 3) 30 4) 35",
                    "Wasafiri: Jtatu 10, Jnne 15, Jtano 20, Alhamisi 25. Ijumaa? 1) 25 2) 28 3) 30 4) 35"),
    hints=[T("How much bigger is each bar than the one before?", "Kila nguzo inazidi iliyotangulia kwa kiasi gani?")],
    delivery=ALL_DELIVERY,
    expected_reasoning="+5 each day, Friday 30. Tests reading a simple bar chart and extending a linear trend.")

add(id="num-p5", domain="numerical_reasoning", difficulty=5, type="open_ended",
    prompt=T("On this balance, 2 mangoes weigh the same as 6 bananas. How many bananas would weigh the same as 3 mangoes? Explain.",
             "Kwenye mizani hii, maembe 2 yana uzito sawa na ndizi 6. Ndizi ngapi zingekuwa na uzito sawa na maembe 3? Eleza."),
    image=num_p5, response_modes=["type", "voice", "draw"],
    text_fallback=T("2 mangoes weigh the same as 6 bananas. 3 mangoes = how many bananas?", "Maembe 2 = ndizi 6 kwa uzito. Maembe 3 = ndizi ngapi?"),
    hints=[T("What does ONE mango weigh, in bananas?", "Embe MOJA lina uzito wa ndizi ngapi?")],
    delivery=ALL_DELIVERY,
    expected_reasoning="1 mango = 3 bananas, so 3 mangoes = 9. Proportional reasoning (unit rate). An answer of 7 or 8 (additive: 'one more mango, add some') is a common, informative error pattern; record it as additive reasoning.")

add(id="num-p6-offlevel", domain="numerical_reasoning", difficulty=7, type="open_ended", tier="bonus_off_level",
    prompt=T("3 chapatis must be shared fairly between 4 children. How much does each child get? You can draw how you would cut them.",
             "Chapati 3 zinagawanywa kwa haki kati ya watoto 4. Kila mtoto anapata kiasi gani? Unaweza kuchora jinsi ungezikata."),
    image=num_p6, response_modes=["draw", "photo", "voice", "type"],
    text_fallback=T("Share 3 chapatis fairly among 4 children. How much each?", "Gawa chapati 3 kwa haki kwa watoto 4. Kila mmoja anapata kiasi gani?"),
    delivery=["web_play", "whatsapp_image", "whatsapp_voice", "facilitator_cards", "paper_photo"],
    expected_reasoning="Each gets three quarters (3/4). Accept 'half and a quarter', or 'cut each chapati into 4, each child gets 3 pieces'. Drawing answers count fully. Off-level: fractions as division is above typical level for this age band.")

# ------------------------------------------------------------ verbal
add(id="vrb-p1", domain="verbal_reasoning", difficulty=1, type="choice",
    prompt=T("Which one does not belong with the others? Why?", "Kipi hakiendani na vingine? Kwa nini?"),
    image=vrb_p1, choices=[T("Mango", "Embe"), T("Orange", "Chungwa"), T("Ball", "Mpira"), T("Banana", "Ndizi")], answer="c",
    text_fallback=T("Which does not belong: 1) mango 2) orange 3) ball 4) banana", "Kipi si cha kundi: 1) embe 2) chungwa 3) mpira 4) ndizi"),
    delivery=ALL_DELIVERY,
    expected_reasoning="Ball (not a fruit / cannot be eaten). Accept any other defensible grouping WITH a reason (e.g. 'banana, because the others are round') and record it as flexible categorisation, a positive signal.")

add(id="vrb-p2", domain="verbal_reasoning", difficulty=3, type="choice", replaces="vrb-01",
    prompt=T("A hoe is to a farmer as a net is to a ... ? Choose one. You can also say why, but you don't have to.",
             "Jembe ni kwa mkulima kama wavu ni kwa ... ? Chagua moja. Unaweza kueleza sababu, lakini si lazima."),
    choices=[T("Fisherman", "Mvuvi"), T("Tailor", "Fundi cherehani"), T("Driver", "Dereva"), T("Teacher", "Mwalimu")], answer="a",
    text_fallback=T("Hoe is to farmer as net is to: 1) fisherman 2) tailor 3) driver 4) teacher", "Jembe kwa mkulima kama wavu kwa: 1) mvuvi 2) fundi cherehani 3) dereva 4) mwalimu"),
    delivery=ALL_DELIVERY,
    expected_reasoning="Fisherman (tool : the worker who uses it). Rewritten from vrb-01, whose 'rain is to farmer' stem mixed a natural condition with a tool, so two options (net, boat) were defensible. Explanation optional and bonus-only, kept from the original design for autistic learners.")

add(id="vrb-p3", domain="verbal_reasoning", difficulty=2, type="order", tier="core",
    prompt=T("These pictures are mixed up. Put them in the right order, then tell the story in your own words.",
             "Picha hizi zimechanganyika. Zipange kwa mpangilio sahihi, kisha usimulie hadithi kwa maneno yako."),
    image=vrb_p3, choices=[T("A", "A"), T("B", "B"), T("C", "C"), T("D", "D")], answer=["b", "d", "a", "c"],
    response_modes=["drag", "type", "voice"],
    text_fallback=T("Put in order: A young plant, B seed in soil, C tall maize with a cob, D small sprout. Reply like: BDAC",
                    "Panga: A mmea mchanga, B mbegu udongoni, C mhindi mrefu wenye gunzi, D chipukizi dogo. Jibu kama: BDAC"),
    delivery=ALL_DELIVERY,
    expected_reasoning="Correct order B, D, A, C (seed, sprout, young plant, maize with cob). The ORDER is the base credit. The told story (typed or voice note) is scored for narrative sequencing, vocabulary and cause-effect words ('then', 'because'). A child who can't write can get full credit by voice note.")

add(id="vrb-p4", domain="verbal_reasoning", difficulty=4, type="open_ended",
    prompt=T("There is a saying: 'Haba na haba hujaza kibaba' (little by little fills the measure). What do you think it means? Tell us about a time it was true.",
             "Kuna methali: 'Haba na haba hujaza kibaba.' Unadhani ina maana gani? Tueleze wakati ambao ilikuwa kweli."),
    image=vrb_p4, response_modes=["voice", "type"],
    text_fallback=T("What does 'Haba na haba hujaza kibaba' mean? Give an example.", "'Haba na haba hujaza kibaba' ina maana gani? Toa mfano."),
    delivery=ALL_DELIVERY,
    expected_reasoning="Small amounts added steadily become large (saving, practice, building). Score abstraction (moving from cups/water to a general idea) and the quality of the personal example. Literal-only answers ('the cup gets full') get partial credit, not zero.")

add(id="vrb-p5", domain="verbal_reasoning", difficulty=3, type="open_ended",
    prompt=T("Kitendawili! 'My house has no door.' What am I? Which clue helped you?",
             "Kitendawili! 'Nyumba yangu haina mlango.' Mimi ni nini? Ni dokezo gani lilikusaidia?"),
    image=vrb_p5, response_modes=["voice", "type"],
    text_fallback=T("Riddle: My house has no door. What am I?", "Kitendawili: Nyumba yangu haina mlango. Mimi ni nini?"),
    hints=[T("Something comes OUT of it, but there is no door to open.", "Kitu hutoka NDANI yake, lakini hakuna mlango wa kufungua.")],
    delivery=ALL_DELIVERY,
    expected_reasoning="Traditional answer: an egg (yai). Accept other defensible answers with a reason (e.g. a coconut, a seed). Score figurative reasoning: mapping 'house' and 'door' to a shell. Riddles are a familiar oral game, which lowers test anxiety.")

# ------------------------------------------------------------ pattern
add(id="pat-p1", domain="pattern_recognition", difficulty=1, type="choice",
    prompt=T("Kuza is making a bead necklace. Which bead comes next?", "Kuza anatengeneza mkufu wa shanga. Shanga ipi inafuata?"),
    image=pat_p1, choices=[T("Red circle", "Duara jekundu"), T("Blue square", "Mraba wa buluu"), T("Yellow triangle", "Pembetatu ya njano"), T("Red square", "Mraba mwekundu")],
    answer="b",
    text_fallback=T("Beads: red circle, blue square, red circle, blue square, red circle, ? 1) red circle 2) blue square 3) yellow triangle 4) red square",
                    "Shanga: duara jekundu, mraba buluu, duara jekundu, mraba buluu, duara jekundu, ? 1) duara jekundu 2) mraba buluu 3) pembetatu njano 4) mraba mwekundu"),
    delivery=ALL_DELIVERY,
    expected_reasoning="Blue square. Shapes AND colours both carry the pattern, so colour-blind learners can still solve it from shape.")

add(id="pat-p2", domain="pattern_recognition", difficulty=3, type="choice",
    prompt=T("1 square needs 4 sticks, 2 squares need 7, 3 squares need 10. How many sticks for 4 squares? What is the rule?",
             "Mraba 1 unahitaji vijiti 4, miraba 2 inahitaji 7, miraba 3 inahitaji 10. Miraba 4 itahitaji vijiti vingapi? Kanuni ni ipi?"),
    image=pat_p2, choices=[T("12", "12"), T("13", "13"), T("14", "14"), T("16", "16")], answer="b",
    text_fallback=T("Stick squares: 1 square=4, 2=7, 3=10. 4 squares=? 1) 12 2) 13 3) 14 4) 16", "Miraba ya vijiti: 1=4, 2=7, 3=10. 4=? 1) 12 2) 13 3) 14 4) 16"),
    hints=[T("Look at how many new sticks you add each time.", "Angalia unaongeza vijiti vipya vingapi kila mara.")],
    response_modes=["tap", "type", "voice", "hands_on"],
    delivery=ALL_DELIVERY + ["hands_on_sticks"],
    expected_reasoning="13 (+3 each square; rule 3n+1). Can be done hands-on with real sticks or matchsticks with a facilitator. Credit stating the general rule (3 x squares + 1) as off-level evidence.")

add(id="pat-p3", domain="pattern_recognition", difficulty=4, type="open_ended", replaces="pat-01",
    prompt=T("What number comes next: 2, 6, 12, 20, 30, ? The dot pictures might help. Tell us the rule you found.",
             "Nambari ipi inafuata: 2, 6, 12, 20, 30, ? Picha za vitone zinaweza kukusaidia. Tueleze kanuni uliyoipata."),
    image=pat_p3, response_modes=["type", "voice", "tap"],
    text_fallback=T("What comes next: 2, 6, 12, 20, 30, ? Tell the rule.", "Nini kinafuata: 2, 6, 12, 20, 30, ? Eleza kanuni."),
    hints=[T("Look at the gaps between the numbers: 4, 6, 8...", "Angalia tofauti kati ya nambari: 4, 6, 8...")],
    delivery=ALL_DELIVERY,
    expected_reasoning="42. Two valid rules: growing differences (+4,+6,+8,+10,+12) or rectangles n x (n+1) shown by the dots (6x7=42). Naming the rectangle rule is a stronger generalisation signal. Reward the rule even if the final number is off.")

add(id="pat-p4", domain="pattern_recognition", difficulty=4, type="choice", tier="core",
    prompt=T("Look at the grid. Which picture fits in the empty box?", "Tazama gridi. Picha ipi inafaa kwenye kisanduku kitupu?"),
    image=pat_p4, choices=[T("A", "A"), T("B", "B"), T("C", "C"), T("D", "D")], answer="c",
    text_fallback=T("Row 1: 1 circle, 2 circles, 3 circles. Row 2: 1 square, 2 squares, 3 squares. Row 3: 1 triangle, 2 triangles, ? 1) 2 triangles 2) 3 squares 3) 3 triangles 4) 3 circles",
                    "Safu 1: duara 1, 2, 3. Safu 2: mraba 1, 2, 3. Safu 3: pembetatu 1, 2, ? 1) pembetatu 2 2) miraba 3 3) pembetatu 3 4) duara 3"),
    hints=[T("What is the same across each row? What changes as you go right?", "Nini kinafanana kwenye kila safu? Nini kinabadilika ukienda kulia?")],
    delivery=ALL_DELIVERY,
    expected_reasoning="C, three triangles (row = shape, column = count). Distractors: A gets shape right but not count; B and D get count right but not shape. The error type tells you which rule was missed.")

add(id="pat-p5", domain="pattern_recognition", difficulty=5, type="choice",
    prompt=T("The arrow turns a little each time. Which arrow comes next?", "Mshale unageuka kidogo kila mara. Mshale upi unafuata?"),
    image=pat_p5, choices=[T("A", "A"), T("B", "B"), T("C", "C"), T("D", "D")], answer="b",
    text_fallback=T("An arrow points right, then down, then left. Next? 1) right 2) up 3) down 4) left", "Mshale unaelekea kulia, kisha chini, kisha kushoto. Unaofuata? 1) kulia 2) juu 3) chini 4) kushoto"),
    delivery=ALL_DELIVERY,
    expected_reasoning="B, pointing up (a quarter turn clockwise each step). Spatial rotation. Choosing D (left again) suggests the child saw 'repeat' rather than 'rotate'.")

add(id="pat-p6-offlevel", domain="pattern_recognition", difficulty=7, type="open_ended", tier="bonus_off_level", replaces="pat-02-offlevel",
    prompt=T("What are the next three symbols? What are the TWO rules working together?", "Alama tatu zinazofuata ni zipi? Kanuni MBILI zinazofanya kazi pamoja ni zipi?"),
    image=pat_p6, response_modes=["type", "voice", "tap"],
    text_fallback=T("sun-sun-moon, moon-moon-sun, sun-sun-moon, moon-moon-sun, ?-?-?", "jua-jua-mwezi, mwezi-mwezi-jua, jua-jua-mwezi, mwezi-mwezi-jua, ?-?-?"),
    delivery=ALL_DELIVERY,
    expected_reasoning="sun-sun-moon. Rule 1: inside each block, two of one symbol then one of the other. Rule 2: blocks alternate. Full credit needs both rules.")

# ------------------------------------------------------------ logical
add(id="log-p1", domain="logical_reasoning", difficulty=2, type="choice",
    prompt=T("Amani is taller than Baraka. Baraka is taller than Chebet. Who is the shortest?",
             "Amani ni mrefu kuliko Baraka. Baraka ni mrefu kuliko Chebet. Nani ni mfupi kuliko wote?"),
    image=log_p1, choices=[T("Amani", "Amani"), T("Baraka", "Baraka"), T("Chebet", "Chebet"), T("We can't tell", "Hatuwezi kujua")], answer="c",
    text_fallback=T("Amani taller than Baraka. Baraka taller than Chebet. Shortest? 1) Amani 2) Baraka 3) Chebet 4) can't tell",
                    "Amani mrefu kuliko Baraka. Baraka mrefu kuliko Chebet. Mfupi zaidi? 1) Amani 2) Baraka 3) Chebet 4) hatujui"),
    delivery=ALL_DELIVERY,
    expected_reasoning="Chebet (transitive ordering). The curtain in the picture stops the child reading heights off the image.")

add(id="log-p2", domain="logical_reasoning", difficulty=4, type="open_ended",
    prompt=T("Kuza walks from Home to School, but must stop at the Market to buy bread. The road from Market to School is closed today (red X). Which way should Kuza go, passing the fewest places?",
             "Kuza anatembea kutoka Nyumbani kwenda Shuleni, lakini lazima asimame Sokoni kununua mkate. Barabara ya Sokoni hadi Shuleni imefungwa leo (X nyekundu). Kuza apite njia gani, akipita sehemu chache zaidi?"),
    image=log_p2, response_modes=["tap", "type", "voice", "draw"],
    text_fallback=T("Roads: Home-Market, Home-Church, Church-Clinic, Market-Clinic, Clinic-School. (Market-School closed.) Go Home to School via Market. Which way?",
                    "Barabara: Nyumbani-Sokoni, Nyumbani-Kanisani, Kanisani-Kliniki, Sokoni-Kliniki, Kliniki-Shuleni. (Sokoni-Shuleni imefungwa.) Nenda Nyumbani hadi Shuleni ukipitia Sokoni. Njia ipi?"),
    hints=[T("First go to the Market. From the Market, which roads are still open?", "Kwanza nenda Sokoni. Kutoka Sokoni, barabara zipi bado ziko wazi?")],
    delivery=ALL_DELIVERY,
    expected_reasoning="Home > Market > Clinic > School. Planning under two constraints (must visit Market, one road closed). Answers that ignore the Market stop (Home > Church > Clinic > School) show partial constraint tracking.")

add(id="log-p3", domain="logical_reasoning", difficulty=4, type="open_ended", replaces="log-01",
    prompt=T("All the children who passed the test studied. Amina did not study. Can we be sure Amina did not pass? Explain your answer.",
             "Watoto wote waliofaulu mtihani walisoma. Amina hakusoma. Je, tunaweza kuwa na uhakika kwamba Amina hakufaulu? Eleza jibu lako."),
    response_modes=["type", "voice", "tap"],
    choices=[T("Yes, we can be sure", "Ndiyo, tuna uhakika"), T("No, we can't be sure", "Hapana, hatuna uhakika")], answer="a",
    text_fallback=T("All who passed studied. Amina did not study. Sure Amina did not pass? 1) yes 2) no. Why?", "Wote waliofaulu walisoma. Amina hakusoma. Una uhakika hakufaulu? 1) ndiyo 2) hapana. Kwa nini?"),
    delivery=ALL_DELIVERY,
    expected_reasoning="FIXED (the v1 guidance contradicted itself). Correct answer: YES, we can be sure. If everyone who passed studied, then anyone who did not study cannot be among those who passed (modus tollens). Full credit: 'yes' plus that reasoning. A 'no' answer that brings in outside knowledge ('maybe she is clever anyway') is reasoning from real life rather than from the rule; give partial credit and note it, since it is a common and informative pattern, not a sign of low ability.")

add(id="log-p4", domain="logical_reasoning", difficulty=4, type="order", tier="core",
    prompt=T("Three friends sit on a bench. Wanjiru sits on the LEFT end. Otieno does NOT sit next to Wanjiru. Who sits in the middle?",
             "Marafiki watatu wanakaa kwenye benchi. Wanjiru anakaa mwisho wa KUSHOTO. Otieno HAKAI karibu na Wanjiru. Nani anakaa katikati?"),
    image=log_p4, choices=[T("Wanjiru", "Wanjiru"), T("Otieno", "Otieno"), T("Fatuma", "Fatuma")], answer=["a", "c", "b"],
    response_modes=["drag", "tap", "type", "voice", "hands_on"],
    text_fallback=T("3 seats. Wanjiru on the left end. Otieno not next to Wanjiru. Who is in the middle? 1) Wanjiru 2) Otieno 3) Fatuma",
                    "Viti 3. Wanjiru mwisho wa kushoto. Otieno si karibu na Wanjiru. Nani katikati? 1) Wanjiru 2) Otieno 3) Fatuma"),
    hints=[T("If Otieno can't be next to Wanjiru, where is the only seat left for him?", "Kama Otieno hawezi kukaa karibu na Wanjiru, kiti kipi pekee kimebaki kwake?")],
    delivery=ALL_DELIVERY + ["hands_on_role_play"],
    expected_reasoning="Order: Wanjiru, Fatuma, Otieno, so Fatuma is in the middle. On WhatsApp/SMS accept 'Fatuma' or the full order. Can be acted out with three children in a group session.")

add(id="log-p5-offlevel", domain="logical_reasoning", difficulty=7, type="open_ended", tier="bonus_off_level", replaces="log-02-offlevel",
    prompt=T("If it is true that 'every learner on the football team also plays music', and Juma plays music, can we be sure Juma is on the football team? And if Juma is NOT on the team, could he still play music? Explain both.",
             "Ikiwa ni kweli kwamba 'kila mwanafunzi aliye kwenye timu ya mpira pia hucheza muziki', na Juma hucheza muziki, je tuna uhakika Juma yuko kwenye timu? Na ikiwa Juma HAYUKO kwenye timu, je bado anaweza kucheza muziki? Eleza yote mawili."),
    response_modes=["type", "voice"],
    text_fallback=T("Every football player plays music. Juma plays music. Is he on the team for sure? If not on the team, can he play music?",
                    "Kila mchezaji wa mpira hucheza muziki. Juma hucheza muziki. Ana uhakika yuko timu? Asipokuwa timu, anaweza kucheza muziki?"),
    delivery=ALL_DELIVERY,
    expected_reasoning="(1) No: playing music does not prove team membership (affirming the consequent). (2) Yes: the rule says nothing about non-members. Full credit needs both directions.")

# ------------------------------------------------------------ working memory
add(id="wmm-p1", domain="working_memory", difficulty=1, type="choice", tier="core",
    prompt=T("Look carefully at the 4 pictures. When they disappear, find the one that is NEW.",
             "Tazama picha 4 kwa makini. Zikipotea, tafuta ile iliyo MPYA."),
    image=wmm_p1_show, image_after=wmm_p1_ask, show_seconds=6,
    show_script=T("mango, key, fish, star", "embe, ufunguo, samaki, nyota"),
    ask_prompt=T("Which one is NEW?", "Kipi ni KIPYA?"),
    choices=[T("Mango", "Embe"), T("Cup", "Kikombe"), T("Fish", "Samaki"), T("Star", "Nyota")], answer="b",
    text_fallback=T("Listen: mango, key, fish, star. Now: mango, cup, fish, star. Which is new? 1) mango 2) cup 3) fish 4) star",
                    "Sikiliza: embe, ufunguo, samaki, nyota. Sasa: embe, kikombe, samaki, nyota. Kipi kipya? 1) embe 2) kikombe 3) samaki 4) nyota"),
    delivery=["web_play", "whatsapp_view_once", "ivr_voice", "facilitator_cards"],
    expected_reasoning="Cup (it replaced the key). On WhatsApp the first image must be sent as VIEW ONCE, or the child can scroll back and it stops being a memory task. On IVR/voice, the lists are spoken once.")

add(id="wmm-p2", domain="working_memory", difficulty=2, type="open_ended", replaces="wmm-01",
    prompt=T("Look at (or listen to) the 5 things in the picture, once. When they're gone, say them BACKWARDS. Did you use a trick to remember?",
             "Tazama (au sikiliza) vitu 5 kwenye picha, mara moja. Vikitoweka, visema KINYUME. Ulitumia mbinu yoyote kukumbuka?"),
    image=wmm_p2_show, show_seconds=8,
    show_script=T("mango, chair, river, seven, blue", "embe, kiti, mto, saba, bluu"),
    ask_prompt=T("Now say the 5 things BACKWARDS, last one first. Did you use a trick to remember?",
                 "Sasa sema vitu 5 KINYUME, cha mwisho kwanza. Ulitumia mbinu yoyote kukumbuka?"), response_modes=["voice", "type", "drag"],
    text_fallback=T("Remember: mango, chair, river, seven, blue. (Next message asks you.)", "Kumbuka: embe, kiti, mto, saba, bluu. (Ujumbe ujao utakuuliza.)"),
    delivery=["web_play", "whatsapp_view_once", "ivr_voice", "facilitator_cards"],
    expected_reasoning="blue, seven, river, chair, mango. v1 asked a WhatsApp/SMS user 'without looking back', which a text chat cannot enforce. Now: timed display (web), view-once media (WhatsApp), or spoken once (IVR). Score accuracy and especially any strategy described (story, chunking, picturing), which is the stronger signal.")

add(id="wmm-p3", domain="working_memory", difficulty=3, type="order",
    prompt=T("Watch Kuza's footsteps on the grid. When they disappear, tap the same path from the green start square.",
             "Tazama nyayo za Kuza kwenye gridi. Zikipotea, gusa njia ileile kuanzia kisanduku cha kijani."),
    image=wmm_p3_show, image_after=wmm_p3_ask, show_seconds=6, answer=["up", "right", "right", "up", "right"],
    show_script=T("up, right, right, up, right", "juu, kulia, kulia, juu, kulia"),
    ask_prompt=T("Now tap the arrows to make the same path from the green square.", "Sasa gusa mishale kutengeneza njia ileile kuanzia kisanduku cha kijani."),
    response_modes=["tap", "voice", "type"],
    text_fallback=T("Listen to the directions once: up, right, right, up, right. Now say them BACKWARDS.",
                    "Sikiliza maelekezo mara moja: juu, kulia, kulia, juu, kulia. Sasa yaseme KINYUME."),
    delivery=["web_play", "ivr_voice", "facilitator_cards"],
    expected_reasoning="Path: up, right, right, up, right (cells 1-6). Visual-spatial memory (Corsi-style). Voice/IVR version uses the spoken directions backwards: right, up, right, right, up. Score cells correct in sequence.")

add(id="wmm-p4", domain="working_memory", difficulty=4, type="open_ended",
    prompt=T("Listen once. At the market Kuza buys 2 tomatoes for 10 shillings each, 1 onion for 5 shillings, and a loaf of bread for 50 shillings. How much did Kuza spend altogether?",
             "Sikiliza mara moja. Sokoni Kuza ananunua nyanya 2 kwa shilingi 10 kila moja, kitunguu 1 kwa shilingi 5, na mkate kwa shilingi 50. Kuza alitumia pesa ngapi kwa jumla?"),
    audio_only=True, response_modes=["voice", "type", "tap"],
    text_fallback=T("(Spoken once) 2 tomatoes at 10, 1 onion at 5, bread at 50. Total?", "(Husemwa mara moja) nyanya 2 kwa 10, kitunguu 1 kwa 5, mkate 50. Jumla?"),
    delivery=["web_play", "whatsapp_voice", "ivr_voice", "facilitator_cards"],
    expected_reasoning="75 (20+5+50). Holding and working on spoken information: no text shown. A total of 65 (counting 1 tomato) is a holding error, not an arithmetic one; note which.")

# ------------------------------------------------------------ creativity
add(id="cre-p1-bonus", domain="creativity", difficulty=3, type="open_ended", tier="bonus_creativity", replaces="cre-01-bonus",
    prompt=T("How many different ways could you use an empty plastic bucket, other than carrying water? Say or list as many as you can.",
             "Ni njia ngapi tofauti unaweza kutumia ndoo tupu ya plastiki, isipokuwa kubeba maji? Sema au orodhesha nyingi kadri uwezavyo."),
    image=cre_p1, response_modes=["voice", "type", "draw"],
    text_fallback=T("List uses for an empty bucket (not carrying water).", "Orodhesha matumizi ya ndoo tupu (si kubeba maji)."),
    delivery=ALL_DELIVERY,
    expected_reasoning="Divergent thinking: fluency (count), flexibility (categories: seat, drum, plant pot, hat, mould), originality (unusual but workable). No right answer.")

add(id="cre-p2-bonus", domain="creativity", difficulty=3, type="draw", tier="bonus_creativity",
    prompt=T("Turn this squiggle into a picture! Draw on it (or on paper and send a photo). Give your picture a name.",
             "Geuza mstari huu kuwa picha! Chora juu yake (au kwenye karatasi kisha tuma picha). Ipe picha yako jina."),
    image=cre_p2, response_modes=["draw", "photo", "voice"],
    text_fallback=T("Draw a picture starting from a curvy line. Send a photo and its name.", "Chora picha ukianza na mstari uliopinda. Tuma picha na jina lake."),
    delivery=["web_play", "whatsapp_image", "paper_photo", "facilitator_cards"],
    expected_reasoning="Figural creativity (Torrance-style incomplete figure). Score originality of what the squiggle becomes, elaboration (detail added), and a title that adds meaning. Scored from the drawing by a vision-capable model or a human; never penalise drawing skill.")

add(id="cre-p3-bonus", domain="creativity", difficulty=4, type="open_ended", tier="bonus_creativity",
    prompt=T("Imagine it rained MILK instead of water for one whole day where you live. What would happen? Think of as many things as you can.",
             "Fikiria mvua ya MAZIWA badala ya maji kwa siku nzima mahali unapoishi. Nini kingetokea? Fikiria mambo mengi kadri uwezavyo."),
    image=cre_p3, response_modes=["voice", "type", "draw"],
    text_fallback=T("If it rained milk for a day where you live, what would happen?", "Kama mvua ya maziwa ingenyesha siku nzima kwako, nini kingetokea?"),
    delivery=ALL_DELIVERY,
    expected_reasoning="Consequences task. Score number and range of consequences (immediate: sticky roads; social: free milk, sellers lose business; second-order: smell, flies, cows). Humour is welcome and often signals originality.")

add(id="cre-p4-bonus", domain="creativity", difficulty=5, type="open_ended", tier="bonus_creativity",
    prompt=T("Carrying water up a steep hill is hard work. Invent something that would make it easier. Draw it, build a model, or explain it.",
             "Kubeba maji kupanda mlima mkali ni kazi ngumu. Buni kitu kitakachofanya iwe rahisi. Kichore, jenga kielelezo, au kieleze."),
    image=cre_p4, response_modes=["draw", "photo", "voice", "type", "hands_on"],
    text_fallback=T("Invent something to make carrying water up a hill easier. Explain how it works.", "Buni kitu cha kurahisisha kubeba maji kupanda mlima. Eleza kinavyofanya kazi."),
    delivery=ALL_DELIVERY + ["paper_photo", "hands_on_model"],
    expected_reasoning="Applied problem-solving and invention. Look for a mechanism (wheels, pulley, rope along the slope, sharing the load, pipe) and whether the child considers real constraints (cost, materials available locally). A photo of a model made from bottle tops or scraps is full evidence.")

# ------------------------------------------------------------ interests (not scored)
add(id="int-p1", domain="interests", difficulty=0, type="multi_choice", tier="warmup_unscored",
    prompt=T("Before we start: which of these do you LOVE doing? Pick as many as you like.",
             "Kabla hatujaanza: unapenda SANA kufanya yapi kati ya haya? Chagua mengi kadri upendavyo."),
    image=int_p1,
    choices=[T("Numbers", "Nambari"), T("Stories and reading", "Hadithi na kusoma"), T("Drawing", "Kuchora"), T("Building things", "Kujenga vitu"),
             T("Music", "Muziki"), T("Nature and animals", "Mazingira na wanyama"), T("Sport", "Michezo"), T("Fixing things", "Kutengeneza vitu")],
    answer=None, response_modes=["tap", "voice", "type"],
    text_fallback=T("What do you love? 1) numbers 2) stories 3) drawing 4) building 5) music 6) nature 7) sport 8) fixing. Send all numbers you like.",
                    "Unapenda nini? 1) nambari 2) hadithi 3) kuchora 4) kujenga 5) muziki 6) mazingira 7) michezo 8) kutengeneza. Tuma nambari zote unazopenda."),
    delivery=ALL_DELIVERY,
    expected_reasoning="NOT SCORED. Warm-up that starts the session with the child, not a test. Used to (a) pick which story theme and which optional items to offer, and (b) pass interests to Layer 2 mentor matching.")


# =============================================================== WRITE
for name, s in IMAGES.items():
    (SVG_DIR / f"{name}.svg").write_text(s)

import cairosvg  # noqa: E402

for name in IMAGES:
    cairosvg.svg2png(url=str(SVG_DIR / f"{name}.svg"), write_to=str(PNG_DIR / f"{name}.png"), output_width=960)

for it in items:
    for k in ("image", "image_after"):
        if k in it:
            it[k + "_png"] = it[k].replace("svg/", "png/").replace(".svg", ".png")

bank = {
    "_README": (
        "Kuza item bank v2, GENERATED by tools/item-bank/build.py (edit there, not here). Backwards compatible with adaptive_item_engine/engine.py: every item keeps id, domain, difficulty, "
        "type, prompt{en,sw}, expected_reasoning, tier. Exactly five items are tier 'core' (one per domain), so the current "
        "5-question session still works unchanged. tier 'pool' items need the adaptive-engine upgrade (pick by domain and "
        "difficulty). New optional fields: image / image_after (+ _png for WhatsApp), show_seconds (memory items), choices + "
        "answer (deterministic scoring, no LLM call needed), show_script / ask_prompt (memory items: what is spoken while "
        "the picture shows, and the question asked once it hides, so the answer is never left on screen), text_fallback (SMS/USSD/IVR wording and the text the LLM scorer "
        "should receive for image items), hints (learning-velocity ladder: record how many were used), response_modes, delivery, "
        "replaces (which v1 item this supersedes), audio_only. Swahili wording is a first draft: have a native-speaking teacher "
        "from the pilot schools review it before use."
    ),
    "session_intro": {
        "en": "Hi, I'm Kuza! These are puzzles and stories, not a test. There's no time limit. Send 'skip' to skip one, 'hint' for a clue, 'repeat' to see it again, or 'pause' to stop and come back later. Answer however you like: tap, type, talk or draw. Some puzzles have no single right answer. We want to see how you think.",
        "sw": "Habari, mimi ni Kuza! Haya ni mafumbo na hadithi, si mtihani. Hakuna muda uliowekwa. Tuma 'ruka' kuruka, 'dokezo' kupata msaada, 'rudia' kuona tena, au 'pumzika' kusimama na kurudi baadaye. Jibu unavyopenda: gusa, andika, ongea au chora. Mafumbo mengine hayana jibu moja sahihi. Tunataka kuona jinsi unavyofikiri.",
    },
    # Deliberately few, unusual words, matched only when they are the WHOLE
    # message, so an ordinary answer ("next", "stop", "again") is never
    # mistaken for a command.
    "control_words": {
        "skip": {"en": ["skip"], "sw": ["ruka"]},
        "hint": {"en": ["hint"], "sw": ["dokezo"]},
        "repeat": {"en": ["repeat"], "sw": ["rudia"]},
        "pause": {"en": ["pause"], "sw": ["pumzika"]},
    },
    "domains": ["numerical_reasoning", "verbal_reasoning", "pattern_recognition", "logical_reasoning", "working_memory"],
    "extra_domains": ["creativity", "interests"],
    "items": items,
}
BANK_PATH.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n")
public = dict(bank)
public.pop("_README")
public["items"] = [{k: v for k, v in it.items() if k not in ("answer", "expected_reasoning")} for it in items]
(PUBLIC / "bank.json").write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n")
print(len(items), "items,", len(IMAGES), "images")
