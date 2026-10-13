"""Tiny SVG drawing kit for Kuza question images.

Style: warm cream card, thick dark-teal outlines (matches the Kuza bird mascot),
flat fills. Every image is 640x400 unless noted, readable on a cheap phone.
"""
from __future__ import annotations

import math

INK = "#0B3B3A"
TEAL = "#0F766E"
TEAL_L = "#5EC4B6"
YEL = "#FBBF24"
ORA = "#F97316"
RED = "#DC2626"
BLUE = "#2563EB"
GRN = "#16A34A"
BRN = "#92400E"
TAN = "#E9B872"
CREAM = "#FFF8E7"
GREY = "#94A3B8"
FONT = "DejaVu Sans, Verdana, Arial, sans-serif"
SW = 4  # stroke width


def svg(body: str, w: int = 640, h: int = 400, title: str = "") -> str:
    t = f"<title>{title}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">{t}'
        f'<rect x="2" y="2" width="{w-4}" height="{h-4}" rx="28" fill="{CREAM}" stroke="{INK}" stroke-width="3"/>'
        f"{body}</svg>"
    )


def text(x, y, s, size=28, fill=INK, anchor="middle", weight="bold"):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" dominant-baseline="middle">{s}</text>')


def circle(x, y, r, fill, stroke=INK, sw=SW):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def rect(x, y, w, h, fill, rx=8, stroke=INK, sw=SW):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def line(x1, y1, x2, y2, stroke=INK, sw=SW, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"{d}/>'


def path(d, fill="none", stroke=INK, sw=SW):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>'


def poly(pts, fill, stroke=INK, sw=SW):
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'


def g(inner, tx=0, ty=0, s=1.0, rot=0):
    return f'<g transform="translate({tx},{ty}) rotate({rot}) scale({s})">{inner}</g>'


def option_label(x, y, letter):
    return circle(x, y, 17, YEL, sw=3) + text(x, y + 1, letter, 20)


# ---------------------------------------------------------------- objects
# Each object is drawn centred on (0,0) at roughly 80px, then placed with g().

def mango():
    return (path("M -26 6 C -30 -26 10 -38 28 -14 C 40 4 20 34 -4 32 C -18 30 -24 20 -26 6 Z", fill=YEL)
            + path("M 4 -30 C 10 -40 22 -42 30 -38 C 24 -30 14 -28 4 -30 Z", fill=GRN, sw=3)
            + path("M -12 -2 C -10 -14 0 -20 8 -20", stroke="#FDE68A", sw=4))


def orange_fruit():
    return (circle(0, 4, 28, ORA) + circle(-9, -5, 3, "#FDBA74", stroke="none")
            + path("M 0 -24 C 4 -34 14 -36 20 -34 C 16 -28 8 -26 0 -24 Z", fill=GRN, sw=3))


def banana():
    return (path("M -34 -10 C -20 30 26 34 38 -6 C 26 12 -10 14 -34 -10 Z", fill="#FDE047")
            + line(-34, -10, -38, -18, sw=5))


def pineapple():
    body = rect(-20, -14, 40, 50, "#F59E0B", rx=18)
    hatch = "".join(line(-14 + i * 10, -8, -4 + i * 10, 28, stroke=BRN, sw=2) for i in range(3))
    leaves = (poly([(-12, -14), (-4, -40), (0, -14)], GRN, sw=3) + poly([(-2, -14), (6, -44), (10, -14)], GRN, sw=3)
              + poly([(6, -14), (18, -36), (16, -12)], GRN, sw=3))
    return leaves + body + hatch


def ball():
    return (circle(0, 0, 30, "#FFFFFF") + path("M -30 0 C -10 -12 10 -12 30 0", stroke=RED, sw=4)
            + path("M -30 0 C -10 12 10 12 30 0", stroke=BLUE, sw=4))


def cup():
    return (path("M -24 -20 L 24 -20 L 18 26 L -18 26 Z", fill=TEAL_L)
            + path("M 24 -10 C 40 -10 40 14 21 14", sw=4))


def key():
    return circle(-18, 0, 14, YEL) + circle(-18, 0, 5, CREAM, sw=3) + rect(-4, -5, 40, 10, YEL, rx=3, sw=3) + rect(24, 4, 6, 10, YEL, rx=1, sw=3)


def star(r=30, fill=YEL):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return poly(pts, fill)


def house():
    return poly([(-30, -4), (0, -30), (30, -4)], RED) + rect(-24, -4, 48, 34, "#FDE68A", rx=2) + rect(-7, 10, 14, 20, BRN, rx=2, sw=3)


def fish():
    return (path("M -30 0 C -14 -22 14 -22 22 0 C 14 22 -14 22 -30 0 Z", fill=BLUE)
            + poly([(20, 0), (38, -16), (38, 16)], BLUE) + circle(-16, -4, 3, INK, sw=1))


def sun(r=22):
    rays = "".join(line(math.cos(a) * (r + 6), math.sin(a) * (r + 6), math.cos(a) * (r + 16), math.sin(a) * (r + 16), sw=4)
                   for a in [i * math.pi / 4 for i in range(8)])
    return rays + circle(0, 0, r, YEL)


def moon():
    return path("M 8 -26 C -22 -24 -24 22 8 26 C -6 14 -6 -14 8 -26 Z", fill="#E2E8F0") + ""


def tree():
    return rect(-6, 0, 12, 34, BRN, rx=3, sw=3) + circle(0, -12, 26, GRN)


def coin(value, r=34):
    fill = "#D4D4D8" if value in (1, 5) else "#FCD34D" if value == 20 else "#E5B66B"
    if value == 10:
        fill = "#CBD5E1"
    return circle(0, 0, r, fill) + circle(0, 0, r - 7, "none", sw=2) + text(0, 2, value, 24)


def chapati(r=40):
    spots = "".join(circle(math.cos(a) * r * 0.5, math.sin(a) * r * 0.5, 5, "#C08A4A", stroke="none")
                    for a in [0.3, 1.9, 3.4, 4.8])
    return circle(0, 0, r, TAN) + spots + circle(0, 0, 6, "#C08A4A", stroke="none")


def child(shirt=TEAL, h=1.0):
    return (circle(0, -46 * h, 16, "#8B5A2B") + rect(-18, -30 * h, 36, 44 * h, shirt, rx=10)
            + line(-9, 14 * h, -9, 40 * h, sw=6) + line(9, 14 * h, 9, 40 * h, sw=6))


def basket():
    return path("M -50 -6 L 50 -6 L 38 36 L -38 36 Z", fill="#B45309") + line(-44, 10, 44, 10, stroke="#78350F", sw=3) + line(-40, 24, 40, 24, stroke="#78350F", sw=3)


def jerrycan():
    return rect(-22, -26, 44, 54, YEL, rx=8) + rect(-6, -36, 12, 12, YEL, rx=3, sw=3) + line(-10, -10, 10, -10, sw=3)


def seed():
    return path("M 0 -12 C 12 -10 14 10 0 14 C -14 10 -12 -10 0 -12 Z", fill="#D97706")


SOIL = lambda: rect(-60, 30, 120, 26, "#A16207", rx=6)


def stage(n):
    """Maize growth stages 0..3 for the story-order item."""
    s = SOIL()
    if n == 0:
        return s + g(seed(), 0, 36, 1.8)
    if n == 1:
        return s + path("M 0 32 C 0 18 2 8 0 0", sw=4) + path("M 0 6 C 14 -8 30 -4 34 2 C 20 10 8 10 0 6 Z", fill=GRN, sw=3) + path("M 0 12 C -14 0 -26 2 -30 8 C -18 14 -8 14 0 12 Z", fill=GRN, sw=3)
    if n == 2:
        return (s + path("M 0 32 L 0 -30", sw=5) + path("M 0 4 C 18 -10 32 -6 40 0 C 26 6 12 8 0 4 Z", fill=GRN, sw=3)
                + path("M 0 -14 C -18 -28 -32 -24 -40 -18 C -26 -12 -12 -10 0 -14 Z", fill=GRN, sw=3))
    return (s + path("M 0 32 L 0 -70", sw=6)
            + path("M 0 8 C 22 -8 38 -4 46 2 C 30 10 14 12 0 8 Z", fill=GRN, sw=3)
            + path("M 0 -20 C -22 -36 -38 -32 -46 -26 C -30 -18 -14 -16 0 -20 Z", fill=GRN, sw=3)
            + path("M 4 -40 C 22 -46 22 -20 6 -14 Z", fill=YEL, sw=3)
            + path("M 0 -70 L -8 -84 M 0 -70 L 0 -88 M 0 -70 L 8 -84", sw=3))


def shape(kind, r=22, fill=TEAL_L):
    if kind == "circle":
        return circle(0, 0, r, fill)
    if kind == "square":
        return rect(-r, -r, 2 * r, 2 * r, fill, rx=3)
    if kind == "triangle":
        return poly([(0, -r * 1.1), (r * 1.05, r * 0.8), (-r * 1.05, r * 0.8)], fill)
    raise ValueError(kind)


def arrow(rot):
    return g(poly([(-26, 8), (6, 8), (6, 22), (30, 0), (6, -22), (6, -8), (-26, -8)], ORA), 0, 0, 1.0, rot)
