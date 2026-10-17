#!/usr/bin/env python3
"""모노톤 목탄 질감 만화풍 모션그래픽 생성기.

벤치에 앉아 생각하는 사람 + 생각풍선("10년의 계획에서 2년이 흘러가고 있다").
만화식 굵은 윤곽선·의상 볼륨·머리카락 뭉치 위에 목탄 질감(워블·끊김·해칭)을 유지해
절차적으로 그리고 ffmpeg로 mp4 인코딩한다.

  python3 make_motion.py stills 1.0 3.0 6.0 9.0 12.5   # 미리보기 PNG
  python3 make_motion.py render                        # out/charcoal_bench.mp4
"""
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 30
DUR = 13.8

INK = np.array([46, 46, 50], np.float32) / 255.0
PAPER = np.array([240, 240, 238], np.float32) / 255.0

FONT_B = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_R = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PREV = os.path.join(HERE, "preview")

# ---------------------------------------------------------------- geometry ---
GROUND = 902
HORIZON = 636

LINE1 = "10년의 계획에서"
LINE2 = "2년이 흘러가고 있다"
TYPING_T0, TYPING_T1 = 7.9, 10.4

P_DY = -22


def _dy(pts, d=P_DY):
    return [(x, y + d) for x, y in pts]


def rot_pts(pts, c, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa,
             c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


HIP = (1206, 656)
BACK = _dy([(1216, 676), (1190, 600), (1140, 528), (1080, 478), (1052, 464)])
CHEST = _dy([(1176, 672), (1116, 620), (1074, 566), (1052, 514), (1046, 488)])
SHOULDER = (1052, 448)
HEAD_C = (1000, 336)
HEAD_TILT = -11.0
# 머리: 뾰족한 앞머리+뒷머리 실루엣 (만화식 머리 뭉치)
HAIR = rot_pts(_dy([(956, 338), (960, 318), (976, 308), (998, 304), (1020, 308), (1038, 320),
                    (1050, 338), (1054, 362), (1048, 390), (1036, 412), (1024, 424),
                    (1014, 440), (1004, 424), (994, 438), (988, 418),
                    (992, 398), (984, 386), (974, 376), (964, 380), (956, 362), (948, 372),
                    (946, 354), (952, 346)]), HEAD_C, HEAD_TILT)
# 얼굴 옆선: 이마→콧등→입술→턱 (만화 프로파일)
FACE = rot_pts(_dy([(952, 344), (944, 358), (940, 368), (928, 382), (936, 390), (932, 398),
                    (936, 404), (938, 416), (946, 428), (960, 438), (978, 444)]), HEAD_C, HEAD_TILT)
NECKLINE = _dy([(1000, 440), (1012, 452), (1024, 468)])
ELBOW = (1002, 674)
WRIST = (984, 472)
HAND = (966, 428)
THIGH = [(1206, 654), (1100, 662), (1000, 668), (912, 678)]
SHIN = [(912, 678), (902, 772), (898, 862)]
FOOT = [(898, 864), (894, 898), (830, 898), (818, 886), (838, 878), (896, 862)]
FAR_LEG = [(1220, 660), (962, 692), (952, 872), (892, 894)]
BUBBLE_C = (500.0, 262.0)
BUBBLE_RX, BUBBLE_RY = 320.0, 168.0
TRAILS = [((902, 320), 22.0), ((868, 298), 13.0), ((840, 280), 7.0)]


def clip01(v):
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def smoothstep(p):
    p = clip01(p)
    return p * p * (3 - 2 * p)


def ease_out_back(p):
    c1, c3 = 1.70158, 2.70158
    p -= 1.0
    return 1 + c3 * p * p * p + c1 * p * p


# ------------------------------------------------------------ stroke utils ---
def densify(pts, step=4.0):
    out = []
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / step))
        for k in range(n):
            t = k / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append((float(pts[-1][0]), float(pts[-1][1])))
    return out


def catmull(pts, samples=10):
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)))
    out.append((float(p[-2][0]), float(p[-2][1])))
    return out


def wobble(pts, amp=1.7, seed=0):
    n = len(pts)
    if n < 2 or amp <= 0:
        return list(pts)
    rng = np.random.default_rng(seed)
    f1, f2 = rng.uniform(0.7, 1.5), rng.uniform(2.0, 3.6)
    p1, p2 = rng.uniform(0, 6.283), rng.uniform(0, 6.283)
    a1, a2 = rng.uniform(0.7, 1.3), rng.uniform(0.35, 0.85)
    idx = np.arange(n)
    off = amp * (a1 * np.sin(2 * np.pi * f1 * idx / n + p1)
                 + a2 * np.sin(2 * np.pi * f2 * idx / n + p2))
    off = off + rng.normal(0, amp * 0.10, n)
    res = []
    for i, (x, y) in enumerate(pts):
        i0, i1 = max(0, i - 1), min(n - 1, i + 1)
        dx, dy = pts[i1][0] - pts[i0][0], pts[i1][1] - pts[i0][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        res.append((x + nx * off[i], y + ny * off[i]))
    return res


def stroke(d, pts, value=(48, 48, 52), alpha=205, width=2.2, wob=1.7,
           seed=0, passes=2, skip=0.05, step=4.0):
    """목탄 선: 여러 번 덧그리고, 군데군데 끊긴다."""
    if len(pts) < 2:
        return
    base = densify(pts, step=step)
    v = tuple(int(c) for c in value)
    for pi in range(passes):
        rnd = random.Random(seed * 977 + pi * 31)
        jp = wobble(base, amp=wob * (1.0 + 0.55 * pi), seed=seed * 131 + pi)
        w0 = max(1.0, width * (1.0 + (pi - 0.5) * 0.30))
        a0 = alpha * (1.0 - 0.20 * pi)
        for i in range(len(jp) - 1):
            if rnd.random() < skip:
                continue
            aa = int(max(0, min(255, a0 * rnd.uniform(0.80, 1.05))))
            ww = int(round(w0 * rnd.uniform(0.85, 1.25)))
            d.line([jp[i], jp[i + 1]], fill=v + (aa,), width=max(1, ww))


def hatch(d, polys, angle, spacing, value=(66, 66, 70), alpha=135, seed=0,
          dash=(16, 26, 11), wob=1.0, width=1.5):
    """다각형 안쪽만 채우는 빗금(교차 해칭용)."""
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, y0 = max(0, int(min(xs)) - 2), max(0, int(min(ys)) - 2)
    x1, y1 = min(W, int(max(xs)) + 3), min(H, int(max(ys)) + 3)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    md = ImageDraw.Draw(m)
    for poly in polys:
        md.polygon([(px - x0, py - y0) for px, py in poly], fill=255)
    mask = np.asarray(m, np.uint8) > 0
    h, w = mask.shape
    rad = math.radians(angle)
    ux, uy = math.cos(rad), math.sin(rad)
    px, py = -uy, ux
    cx, cy = w / 2.0, h / 2.0
    diag = math.hypot(w, h)
    n = int(diag / spacing) + 2
    rnd = random.Random(seed)
    v = tuple(int(c) for c in value)
    for i in range(-n // 2 - 1, n // 2 + 2):
        ox, oy = cx + px * i * spacing, cy + py * i * spacing
        lo, hi = -diag, diag
        ok = True
        for o, u, lim in ((ox, ux, w), (oy, uy, h)):
            if abs(u) < 1e-6:
                if o < 0 or o > lim:
                    ok = False
                    break
            else:
                a, b = (0 - o) / u, (lim - o) / u
                if a > b:
                    a, b = b, a
                lo, hi = max(lo, a), min(hi, b)
        if not ok or hi - lo < 4:
            continue
        step = 3.0
        ns = int((hi - lo) / step) + 1
        on = []
        for k in range(ns + 1):
            t = lo + k * step
            xi, yi = int(ox + ux * t), int(oy + uy * t)
            on.append(0 <= xi < w and 0 <= yi < h and mask[yi, xi])
        k = 0
        while k < len(on):
            if not on[k]:
                k += 1
                continue
            j = k
            while j < len(on) and on[j]:
                j += 1
            t_cur = lo + k * step
            t_end_run = lo + (j - 1) * step
            while t_cur < t_end_run - 3:
                dl = rnd.uniform(dash[0], dash[1])
                gl = rnd.uniform(dash[2] * 0.6, dash[2] * 1.9)
                te = min(t_cur + dl, t_end_run)
                if te - t_cur > 4:
                    jx = rnd.uniform(-wob, wob)
                    jy = rnd.uniform(-wob, wob)
                    aa = int(alpha * rnd.uniform(0.65, 1.0))
                    d.line([(ox + ux * t_cur + jx + x0, oy + uy * t_cur + jy + y0),
                            (ox + ux * te + jx + x0, oy + uy * te + jy + y0)],
                           fill=v + (aa,),
                           width=max(1, int(round(rnd.uniform(width * 0.7, width * 1.35)))))
                t_cur = te + gl
            k = j


def fill_ink(d, polys, angle, value=(70, 70, 74), alpha=90, seed=0,
             spacing=3.4, width=2.2, wob=1.0):
    """만화의 단색 면(블랙/그레이): 틈 없이 겹쳐 그린 목탄 채움."""
    hatch(d, polys, angle, spacing, value=value, alpha=alpha, seed=seed,
          dash=(26, 64, 0), wob=wob, width=width)


def ellipse_poly(cx, cy, rx, ry, n=28, rot=0.0):
    pts = []
    cr, sr = math.cos(rot), math.sin(rot)
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return pts


def blob(cx, cy, rx, ry, bumps=7, seed=0, amp=0.085, n=420):
    rng = random.Random(seed)
    ph = rng.uniform(0, 6.28)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1.0 + amp * math.cos(bumps * a + ph) + 0.035 * math.sin(1.7 * a + ph * 2)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    return pts


# ------------------------------------------------------------------ layers ---
class Layer:
    def __init__(self, name, seed, reveal=None, direction=(1, 0), opacity=1.0,
                 shift=None, blur=0.5, ink=INK, gain=1.0):
        self.name = name
        self.img = Image.new("RGB", (W, H), (255, 255, 255))
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.seed = seed
        self.reveal = reveal
        self.direction = direction
        self.opacity = opacity
        self.shift_fn = shift
        self.blur = blur
        self.ink = ink
        self.gain = gain
        self.ready = False

    def prep(self):
        if self.ready:
            return
        if self.blur > 0:
            self.img = self.img.filter(ImageFilter.GaussianBlur(self.blur))
        if self.gain != 1.0:
            g = self.gain
            self.img = self.img.point(lambda v: int(max(0, min(255, 255 - (255 - v) * g))))
        a = 1.0 - np.asarray(self.img.convert("L"), np.float32) / 255.0
        ys, xs = np.nonzero(a > 0.015)
        if len(ys) == 0:
            self.bbox = (0, 0, 1, 1)
            self.alpha = a
            self.order = None
            self.ready = True
            return
        x0 = max(0, int(xs.min()) - 3)
        y0 = max(0, int(ys.min()) - 3)
        x1 = min(W, int(xs.max()) + 4)
        y1 = min(H, int(ys.max()) + 4)
        self.bbox = (x0, y0, x1, y1)
        self.alpha = a
        if self.reveal:
            self.order = build_order(x1 - x0, y1 - y0, self.direction, self.seed)
        else:
            self.order = None
        self.ready = True


def build_order(w, h, direction, seed):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = direction
    nrm = math.hypot(dx, dy) or 1.0
    proj = (xx / max(1, w - 1)) * dx / nrm + (yy / max(1, h - 1)) * dy / nrm
    proj = (proj - proj.min()) / (float(proj.max() - proj.min()) + 1e-6)
    rng = np.random.default_rng(seed)
    nz = rng.normal(size=(max(2, h // 30), max(2, w // 30))).astype(np.float32)
    nz = (nz - nz.min()) / (float(nz.max() - nz.min()) + 1e-6)
    nz = np.asarray(Image.fromarray((nz * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR),
                    np.float32) / 255.0
    return np.clip(proj * 0.90 + nz * 0.10, 0, 1).astype(np.float32)


def shift2d(a, dy, dx):
    if abs(dy) < 1e-4 and abs(dx) < 1e-4:
        return a
    iy, ix = int(math.floor(dy)), int(math.floor(dx))
    fy, fx = dy - iy, dx - ix
    r = lambda k, m: np.roll(np.roll(a, k, 0), m, 1)
    return (r(iy, ix) * (1 - fy) * (1 - fx) + r(iy + 1, ix) * fy * (1 - fx)
            + r(iy, ix + 1) * (1 - fy) * fx + r(iy + 1, ix + 1) * fy * fx)


def composite(out, canvas, bbox, ink=(INK[0], INK[1], INK[2])):
    x0, y0, x1, y1 = bbox
    sub = out[y0:y1, x0:x1]
    sub *= (1.0 - canvas[..., None])
    sub += np.asarray(ink, np.float32)[None, None, :] * canvas[..., None]


# ------------------------------------------------------------ scene builder --
def build_scene():
    L = {}

    def new(name, **kw):
        ly = Layer(name, kw.pop("seed", abs(hash(name)) % 9999), **kw)
        L[name] = ly
        return ly

    # ---- 배경: 지평선 + 바닥 해칭 + 잔디/낙엽/새
    bg = new("bg", seed=11, reveal=(0.7, 2.1), direction=(1.0, 0.25), blur=0.6)
    d = bg.d
    stroke(d, [(90, HORIZON), (600, HORIZON - 8), (1150, HORIZON + 4), (1830, HORIZON - 6)],
           value=(120, 120, 124), alpha=110, width=1.6, wob=1.4, seed=3, passes=1, skip=0.16)
    hatch(d, [[(20, HORIZON + 6), (1900, HORIZON - 2), (1900, 760), (20, 766)]],
          angle=2, spacing=26, value=(150, 150, 154), alpha=70, seed=5,
          dash=(10, 34, 22), width=1.3)
    hatch(d, [[(0, 768), (1920, 762), (1920, 1080), (0, 1080)]],
          angle=3, spacing=23, value=(135, 135, 139), alpha=85, seed=6,
          dash=(14, 40, 26), width=1.4)
    rnd = random.Random(21)
    for i in range(120):  # 바닥 흩뿌린 짧은 선
        x = rnd.uniform(10, 1910)
        y = rnd.uniform(770, 1060)
        ln = rnd.uniform(6, 26)
        stroke(d, [(x, y), (x + ln, y + rnd.uniform(-3, 3))], value=(120, 120, 124),
               alpha=rnd.randint(50, 105), width=1.3, wob=0.8,
               seed=200 + i, passes=1, skip=0.0, step=6)
    # 잔디 포기
    for (x, y, s, sd) in ((598, 906, 1.0, 31), (1548, 912, 0.85, 32), (352, 920, 0.8, 33),
                          (1760, 906, 0.7, 34)):
        for k in range(5):
            a = -math.pi / 2 + (k - 2) * 0.30
            ln = (30 + 8 * (2 - abs(k - 2))) * s
            stroke(d, [(x, y), (x + ln * math.cos(a) * 0.6, y + ln * math.sin(a))],
                   value=(72, 72, 76), alpha=170, width=1.5, wob=1.0,
                   seed=sd * 10 + k, passes=1, skip=0.06, step=5)
    # 낙엽
    for (x, y, r, sd) in ((486, 934, 15, 41), (1092, 952, 13, 42), (1424, 930, 14, 43),
                          (700, 972, 11, 44)):
        p = ellipse_poly(x, y, r, r * 0.55, n=20, rot=-0.4)
        stroke(d, p + [p[0]], value=(86, 86, 90), alpha=150, width=1.4, wob=0.9,
               seed=sd, passes=1, skip=0.05, step=5)
        hatch(d, [p], angle=25, spacing=5, value=(92, 92, 96), alpha=90, seed=sd + 5,
              dash=(6, 12, 6), width=1.1)
    # 멀리 나는 새
    for (x, y, s) in ((1586, 236, 26), (1660, 276, 17)):
        for sgn in (-1, 1):
            stroke(d, [(x, y), (x + sgn * s * 0.5, y - s * 0.42), (x + sgn * s, y - s * 0.12)],
                   value=(78, 78, 82), alpha=165, width=1.5, wob=1.0,
                   seed=int(x + sgn), passes=1, skip=0.04, step=5)
    # 먼 나무(왼쪽) + 덤불(오른쪽) — 만화 배경 요소
    stroke(d, [(240, 902), (248, 796), (244, 690), (248, 640)], value=(84, 84, 88), alpha=200,
           width=3.6, wob=1.4, seed=71)
    stroke(d, [(266, 900), (260, 800), (256, 700), (258, 648)], value=(118, 118, 122), alpha=120,
           width=2.0, wob=1.2, seed=72, passes=1)
    can = blob(252, 566, 96, 74, bumps=8, seed=73)
    stroke(d, can + [can[0]], value=(72, 72, 76), alpha=190, width=2.4, wob=1.4,
           seed=74, passes=2, step=6)
    hatch(d, [can], angle=-35, spacing=12, value=(130, 130, 134), alpha=60, seed=75,
          dash=(14, 30, 12), width=1.4)
    bsh = blob(1690, 812, 66, 26, bumps=6, seed=76, amp=0.12)
    stroke(d, bsh + [bsh[0]], value=(84, 84, 88), alpha=170, width=2.0, wob=1.2,
           seed=77, passes=1, step=5)
    hatch(d, [bsh], angle=15, spacing=9, value=(124, 124, 128), alpha=70, seed=78,
          dash=(10, 24, 10), width=1.2)
    for (gx, gy) in ((1652, 834), (1698, 838), (1726, 830)):
        stroke(d, [(gx, gy), (gx - 4, gy + 13)], value=(110, 110, 114), alpha=110,
               width=1.3, wob=0.5, seed=gx % 83, passes=1, step=4)

    # ---- 벤치
    bench = new("bench", seed=12, reveal=(1.9, 3.15), direction=(1.0, 0.15), blur=0.55, gain=1.08)
    d = bench.d
    SX0, SX1, SY0, SY1 = 656, 1564, 712, 740
    BX0, BX1, BY0 = 1440, 1516, 498
    stroke(d, [(SX0, SY0), (SX1, SY0)], value=(44, 44, 48), alpha=225, width=3.4, wob=1.8, seed=13)
    stroke(d, [(SX0, SY1), (SX1, SY1)], value=(58, 58, 62), alpha=190, width=2.2, wob=1.8, seed=14)
    stroke(d, [(SX0, SY0), (SX0, SY1)], value=(58, 58, 62), alpha=190, width=2.2, wob=1.4, seed=15)
    stroke(d, [(BX0, BY0), (BX1, BY0)], value=(46, 46, 50), alpha=210, width=2.4, wob=1.5, seed=16)
    stroke(d, [(BX0, BY0), (BX0, SY0)], value=(44, 44, 48), alpha=215, width=2.6, wob=1.7, seed=17)
    stroke(d, [(BX1, BY0 - 4), (BX1, SY0)], value=(74, 74, 78), alpha=170, width=2.0, wob=1.6, seed=18)
    for yy in (556, 612, 668):
        stroke(d, [(BX0, yy), (BX1, yy)], value=(92, 92, 96), alpha=155, width=1.6, wob=1.0, seed=19 + yy)
    fill_ink(d, [[(BX0, BY0), (BX1, BY0), (BX1, SY0), (BX0, SY0)]], angle=86,
             value=(104, 104, 108), alpha=60, seed=22, spacing=4.2, width=2.0)
    hatch(d, [[(BX0, BY0), (BX1, BY0), (BX1, SY0), (BX0, SY0)]], angle=86, spacing=9,
          value=(122, 122, 126), alpha=75, seed=95, dash=(18, 40, 8), width=1.3)
    hatch(d, [[(SX0 + 6, SY0 + 3), (SX1 - 24, SY0 + 3), (SX1 - 24, SY1 - 3), (SX0 + 6, SY1 - 3)]],
          angle=4, spacing=7, value=(126, 126, 130), alpha=70, seed=20, dash=(18, 40, 12), width=1.3)
    for (xa, xb, s) in ((706, 734, 21), (1444, 1472, 22)):
        stroke(d, [(xa, SY1), (xb - 6, 902)], value=(48, 48, 52), alpha=208, width=2.4, wob=1.6, seed=s)
        stroke(d, [(xb, SY1), (xa + 8, 902)], value=(70, 70, 74), alpha=165, width=1.9, wob=1.6, seed=s + 1)
    stroke(d, [(716, 836), (1456, 850)], value=(88, 88, 92), alpha=160, width=1.9, wob=1.6, seed=25)
    stroke(d, [(716, 836), (718, 894)], value=(96, 96, 100), alpha=145, width=1.7, wob=1.2, seed=26)
    # 바닥 그림자: 단색에 가까운 회색 덩어리(만화식)
    fill_ink(d, [ellipse_poly(1090, 906, 500, 24, n=30)], angle=3, value=(124, 124, 128),
             alpha=50, seed=27, spacing=3.6, width=2.0)
    fill_ink(d, [ellipse_poly(1090, 906, 310, 16, n=26)], angle=3, value=(102, 102, 106),
             alpha=70, seed=28, spacing=3.2, width=2.0)
    # 좌판 아래 단면
    fill_ink(d, [[(664, 744), (1548, 744), (1548, 754), (664, 754)]], angle=3,
             value=(94, 94, 98), alpha=70, seed=29, spacing=3.0, width=2.0)

    # ---- 사람 (다리 → 몸통 → 머리 → 팔)
    legs = new("legs", seed=31, reveal=(3.0, 3.75), direction=(1.0, 0.5), blur=0.5, gain=1.16)
    d = legs.d
    # 오른(먼) 다리: 옅은 바지 외곽 + 접힘 + 구두
    stroke(d, FAR_LEG, value=(124, 124, 128), alpha=145, width=2.2, wob=1.6, seed=32, passes=1)
    stroke(d, [(1212, 678), (972, 708), (946, 878), (888, 892)],
           value=(132, 132, 136), alpha=105, width=1.7, wob=1.4, seed=33, passes=1)
    for (xa, ya, xb, yb) in ((1146, 686, 1140, 700), (1010, 702, 1004, 716), (958, 782, 944, 784)):
        stroke(d, [(xa, ya), (xb, yb)], value=(136, 136, 140), alpha=95, width=1.5,
               wob=0.6, seed=xa % 97, passes=1, step=5)
    fshoe = [(960, 866), (950, 888), (920, 896), (884, 894), (878, 882), (896, 872), (930, 866)]
    stroke(d, fshoe + [fshoe[0]], value=(112, 112, 116), alpha=160, width=2.0, wob=1.1,
           seed=85, passes=1, step=5)
    hatch(d, [fshoe], angle=18, spacing=6, value=(128, 128, 132), alpha=75, seed=86,
          dash=(8, 18, 6), width=1.2)
    # 왼(가까운) 다리: 바지 볼륨(닫힌 형태) + 무릎 주름
    OUT_LEG = [(1216, 650), (1096, 660), (990, 668), (902, 678), (894, 770), (894, 858)]
    IN_LEG = [(1208, 690), (1074, 696), (966, 702), (920, 706), (918, 796), (910, 856)]
    trouser = catmull(OUT_LEG, 8) + list(reversed(catmull(IN_LEG, 8)))
    hatch(d, [trouser], angle=80, spacing=8, value=(118, 118, 122), alpha=95, seed=39,
          dash=(16, 34, 8), width=1.5)
    stroke(d, catmull(OUT_LEG, 8), value=(42, 42, 46), alpha=222, width=3.2, wob=1.6, seed=34)
    stroke(d, catmull(IN_LEG, 8), value=(76, 76, 80), alpha=170, width=2.0, wob=1.3, seed=35, passes=1)
    stroke(d, [(894, 858), (910, 856)], value=(80, 80, 84), alpha=160, width=1.8,
           wob=0.6, seed=36, passes=1, step=4)
    for (xa, ya, xb, yb) in ((938, 690, 922, 696), (948, 712, 932, 716)):
        stroke(d, [(xa, ya), (xb, yb)], value=(96, 96, 100), alpha=120, width=1.6,
               wob=0.7, seed=xa % 89, passes=1, step=5)
    # 왼 구두: 짙은 채움 + 밑창
    stroke(d, FOOT + [FOOT[0]], value=(46, 46, 50), alpha=222, width=3.0, wob=1.3, seed=41)
    fill_ink(d, [FOOT + [FOOT[0]]], angle=-24, value=(88, 88, 92), alpha=95, seed=87,
             spacing=3.6, width=2.2)
    stroke(d, [(894, 896), (836, 896)], value=(40, 40, 44), alpha=225, width=3.4, wob=1.0, seed=88)
    # 앉은 자세: 엉덩이가 좌판에 닿는 곡선
    stroke(d, catmull([(1216, 652), (1240, 670), (1250, 704), (1206, 712), (1140, 713)], 8),
           value=(58, 58, 62), alpha=195, width=2.4, wob=1.5, seed=38)

    torso = new("torso", seed=41, reveal=(3.5, 4.45), direction=(0.15, 1.0), blur=0.5, gain=1.16)
    d = torso.d
    stroke(d, catmull(BACK, 12), value=(40, 40, 44), alpha=218, width=3.0, wob=1.9, seed=42)
    stroke(d, catmull(CHEST, 10), value=(58, 58, 62), alpha=190, width=2.3, wob=1.7, seed=43)
    stroke(d, catmull([(1024, 468), (1046, 462), (1068, 474), (1080, 490)], 8),
           value=(48, 48, 52), alpha=205, width=2.3, wob=1.4, seed=44)
    stroke(d, catmull([SHOULDER, (1078, 486), (1100, 508), (1112, 534)], 8),
           value=(76, 76, 80), alpha=155, width=1.8, wob=1.3, seed=45, passes=1)
    hatch(d, [BACK + list(reversed(CHEST))], angle=-40, spacing=8,
          value=(120, 120, 124), alpha=100, seed=46, dash=(16, 34, 8), width=1.5)
    hatch(d, [BACK + list(reversed(CHEST))], angle=34, spacing=13,
          value=(132, 132, 136), alpha=70, seed=47, dash=(14, 30, 10), width=1.3)
    # 옷감 디테일: 옷깃·단·소매선·턱밑 그림자 (만화 의상 기호)
    stroke(d, _dy([(1022, 468), (1044, 478), (1064, 486)]), value=(52, 52, 56), alpha=200,
           width=2.4, wob=1.0, seed=90)
    stroke(d, catmull(_dy([(1064, 508), (1090, 560), (1120, 620), (1148, 668)]), 6),
           value=(112, 112, 116), alpha=110, width=1.6, wob=1.1, seed=91, passes=1)
    stroke(d, _dy([(1178, 676), (1198, 682), (1216, 678)]), value=(48, 48, 52), alpha=210,
           width=2.8, wob=1.1, seed=92)
    stroke(d, _dy([(1052, 470), (1066, 496), (1076, 520)]), value=(118, 118, 122), alpha=100,
           width=1.5, wob=0.9, seed=93, passes=1)
    hatch(d, [_dy([(1008, 492), (1050, 500), (1046, 522), (1008, 514)])], angle=-24, spacing=5,
          value=(120, 120, 124), alpha=85, seed=94, dash=(10, 22, 6), width=1.3)

    head = new("head", seed=51, reveal=(4.2, 4.95), direction=(0.25, 1.0), blur=0.45, gain=1.16)
    d = head.d
    HP = lambda pts: rot_pts(_dy(pts), HEAD_C, HEAD_TILT)
    # 얼굴 옆선: 이마→콧등→입술→턱 (만화 프로파일)
    stroke(d, catmull(FACE, 9), value=(40, 40, 44), alpha=225, width=3.0, wob=1.2, seed=54)
    # 머리카락: 진한 목탄 채움 + 뾰족 윤곽
    fill_ink(d, [HAIR], angle=72, value=(58, 58, 62), alpha=120, seed=61, spacing=3.0, width=2.4)
    fill_ink(d, [HAIR], angle=12, value=(72, 72, 76), alpha=55, seed=62, spacing=4.4, width=2.0)
    for (pts, sd) in (([(986, 318), (1002, 332), (1014, 352), (1020, 376)], 66),
                      ([(966, 326), (980, 342), (990, 362), (994, 384)], 67)):
        stroke(d, catmull(HP(pts), 6), value=(104, 104, 108), alpha=110, width=1.6,
               wob=0.9, seed=sd, passes=1, step=5)
    stroke(d, HAIR + [HAIR[0]], value=(40, 40, 44), alpha=225, width=3.0, wob=1.3, seed=52)
    # 귀
    stroke(d, catmull(HP([(994, 394), (1004, 396), (1006, 408), (998, 414), (992, 408)]), 6),
           value=(64, 64, 68), alpha=185, width=2.0, wob=0.9, seed=63, passes=1)
    stroke(d, HP([(1000, 398), (1003, 407)]), value=(92, 92, 96), alpha=135, width=1.5,
           wob=0.5, seed=64, passes=1, step=4)
    # 눈썹·감은 눈·입
    stroke(d, HP([(948, 366), (964, 362)]), value=(58, 58, 62), alpha=195, width=2.2,
           wob=0.8, seed=57)
    stroke(d, catmull(HP([(948, 386), (956, 392), (964, 386)]), 5), value=(48, 48, 52),
           alpha=215, width=2.3, wob=0.7, seed=58)
    stroke(d, HP([(964, 386), (968, 384)]), value=(48, 48, 52), alpha=180, width=1.6,
           wob=0.4, seed=68, passes=1, step=4)
    stroke(d, HP([(938, 404), (947, 405)]), value=(84, 84, 88), alpha=165, width=1.7,
           wob=0.5, seed=59, passes=1, step=4)
    # 목·턱밑
    stroke(d, catmull(NECKLINE, 6), value=(54, 54, 58), alpha=195, width=2.2, wob=1.0, seed=55)
    stroke(d, HP([(982, 448), (998, 436)]), value=(104, 104, 108), alpha=135, width=1.6,
           wob=0.9, seed=60, passes=1, step=5)
    # 볼 옆 음영
    hatch(d, [HP([(948, 408), (968, 420), (964, 432), (946, 424)])], angle=44, spacing=6,
          value=(122, 122, 126), alpha=70, seed=56, dash=(10, 20, 8), width=1.2)

    arm = new("arm", seed=71, reveal=(4.8, 5.55), direction=(0.6, 0.8), blur=0.5, gain=1.20)
    d = arm.d
    # 위팔 소매: 닫힌 형태 + 옅은 채움
    UP_OUT = [(1062, 464), (1050, 540), (1042, 600), (1040, 634)]
    UP_IN = [(1040, 470), (1024, 548), (1018, 608), (1024, 636)]
    sleeve = catmull(UP_OUT, 10) + list(reversed(catmull(UP_IN, 10)))
    hatch(d, [sleeve], angle=-58, spacing=8, value=(126, 126, 130), alpha=78, seed=74,
          dash=(14, 32, 8), width=1.4)
    stroke(d, catmull(UP_OUT, 10), value=(44, 44, 48), alpha=215, width=2.8, wob=1.5, seed=72)
    stroke(d, catmull(UP_IN, 10), value=(78, 78, 82), alpha=160, width=1.9, wob=1.3, seed=73, passes=1)
    stroke(d, [(1040, 634), (1024, 636)], value=(56, 56, 60), alpha=185, width=2.2,
           wob=0.8, seed=75, passes=1, step=4)
    # 아래팔: 팔꿈치에서 무릎 위로 (닫힌 형태)
    FO_OUT = [(1040, 636), (1000, 654), (962, 662), (936, 660)]
    FO_IN = [(1032, 654), (996, 672), (958, 682), (934, 682)]
    fore = catmull(FO_OUT, 9) + list(reversed(catmull(FO_IN, 9)))
    hatch(d, [fore], angle=-18, spacing=8, value=(128, 128, 132), alpha=68, seed=78,
          dash=(12, 30, 8), width=1.3)
    stroke(d, catmull(FO_OUT, 9), value=(42, 42, 46), alpha=215, width=2.6, wob=1.4, seed=76)
    stroke(d, catmull(FO_IN, 9), value=(84, 84, 88), alpha=150, width=1.8, wob=1.2, seed=77, passes=1)
    # 무릎을 감싼 주먹
    hand_poly = [(938, 658), (918, 646), (900, 652), (893, 668), (901, 681), (921, 683),
                 (938, 676)]
    stroke(d, hand_poly + [hand_poly[0]], value=(40, 40, 44), alpha=215, width=2.5,
           wob=1.0, seed=79)
    hatch(d, [hand_poly], angle=32, spacing=6, value=(104, 104, 108), alpha=85,
          seed=82, dash=(8, 18, 6), width=1.2)
    stroke(d, catmull([(936, 662), (922, 656), (912, 660)], 5), value=(90, 90, 94), alpha=150,
           width=1.7, wob=0.6, seed=83, passes=1, step=5)
    for k in range(3):
        xx = 902 + k * 11
        stroke(d, [(xx, 674), (xx - 5, 690)], value=(96, 96, 100), alpha=140,
               width=1.4, wob=0.6, seed=84 + k, passes=1)

    # ---- 생각풍선 꼬리 + 구름
    for i, (c, r) in enumerate(TRAILS):
        ly = new("trail%d" % i, seed=81 + i)
        q = ellipse_poly(c[0], c[1], r, r * 0.94, n=22, rot=0.3 * i)
        stroke(ly.d, q + [q[0]], value=(48, 48, 52), alpha=200, width=2.0, wob=1.0,
               seed=81 + i, passes=2)
    cloud = new("cloud", seed=91, blur=0.5)
    q = blob(BUBBLE_C[0], BUBBLE_C[1], BUBBLE_RX, BUBBLE_RY, bumps=9, seed=92)
    stroke(cloud.d, q + [q[0]], value=(40, 40, 44), alpha=218, width=2.8, wob=1.6,
           seed=93, passes=2, skip=0.03, step=6)
    q2 = blob(BUBBLE_C[0], BUBBLE_C[1] + 4, BUBBLE_RX * 0.985, BUBBLE_RY * 0.985,
              bumps=9, seed=92)
    stroke(cloud.d, q2 + [q2[0]], value=(120, 120, 124), alpha=110, width=1.6, wob=1.4,
           seed=94, passes=1, skip=0.12, step=6)

    for ly in L.values():
        ly.prep()
    return L


# ------------------------------------------------------------- motion funcs --
def person_bob(t):
    w = smoothstep((t - 5.6) / 1.6)
    ph = 2 * math.pi * 0.30 * (t - 5.6)
    return (0.0, w * 1.15 * math.sin(ph))


def head_bob(t):
    w = smoothstep((t - 5.6) / 1.6)
    ph = 2 * math.pi * 0.30 * (t - 5.6)
    return (w * 1.2 * math.sin(2 * math.pi * 0.17 * t + 0.6),
            w * (1.15 * math.sin(ph) + 0.9 * math.sin(ph + 1.1)))


def legs_bob(t):
    dx, dy = person_bob(t)
    return (dx * 0.35, dy * 0.35)


def cloud_motion(t):
    t0 = 6.75
    if t < t0:
        return None
    p = clip01((t - t0) / 0.62)
    s = ease_out_back(p) if p < 1 else 1.0
    s *= 1.0 + 0.010 * math.sin(2 * math.pi * 0.45 * (t - t0))
    dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
    dx = 1.4 * math.sin(2 * math.pi * 0.28 * (t - t0))
    return (s, dx, dy)


def trail_motion(i):
    def f(t):
        t0 = 6.05 + i * 0.30
        if t < t0:
            return None
        p = clip01((t - t0) / 0.42)
        s = ease_out_back(p) if p < 1 else 1.0
        s *= 1.0 + 0.06 * math.sin(2 * math.pi * 0.45 * (t - t0) - i * 0.8)
        dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
        return (s, 0.0, dy)
    return f


def pop_composite(out, layer, scale, cx, cy, dx=0.0, dy=0.0, fade=1.0):
    """bbox 크롭 위에서 중심 스케일 + 이동 적용. fade(0~1)로 팝업 알파 조절."""
    x0, y0, x1, y1 = layer.bbox
    pad = 90
    px0, py0 = max(0, x0 - pad), max(0, y0 - pad)
    px1, py1 = min(W, x1 + pad), min(H, y1 + pad)
    crop = layer.img.crop((px0, py0, px1, py1))
    cw, ch = crop.size
    mcx, mcy = cx - px0, cy - py0
    inv = 1.0 / max(scale, 1e-4)
    mat = (inv, 0.0, mcx - mcx * inv, 0.0, inv, mcy - mcy * inv)
    tcrop = crop.transform((cw, ch), Image.AFFINE, mat, resample=Image.BILINEAR, fillcolor=(255, 255, 255))
    a = 1.0 - np.asarray(tcrop.convert("L"), np.float32) / 255.0
    a = a * layer.opacity * fade
    if abs(dx) > 0.01 or abs(dy) > 0.01:
        a = shift2d(a, dy, dx)
    composite(out, a, (px0, py0, px1, py1))


def layer_canvas(layer, t):
    x0, y0, x1, y1 = layer.bbox
    if layer.reveal:
        t0, t1 = layer.reveal
        if t <= t0:
            return None
        r = smoothstep((t - t0) / (t1 - t0))
        thresh = -0.12 + 1.30 * r
        av = np.clip((thresh - layer.order) / 0.09, 0, 1)
        if av.max() <= 0.002:
            return None
        a = layer.alpha[y0:y1, x0:x1] * av
    else:
        a = layer.alpha[y0:y1, x0:x1]
    if layer.opacity != 1.0:
        a = a * layer.opacity
    return a


def draw_dust(out, dust, t):
    for (x0, y0, sp, amp, ph, r, a) in dust:
        y = (y0 - sp * t * 26) % (H + 120) - 60
        x = x0 + amp * math.sin(2 * math.pi * 0.12 * t + ph)
        rr = max(1, int(r))
        x0i, y0i = int(x), int(y)
        if not (0 <= x0i < W and 3 <= y0i < H - 3):
            continue
        k = max(1, rr * 2 + 1)
        ax0, ax1 = max(0, x0i - k), min(W, x0i + k + 2)
        ay0, ay1 = max(0, y0i - k), min(H, y0i + k + 2)
        gy, gx = np.mgrid[ay0:ay1, ax0:ax1].astype(np.float32)
        d2 = ((gx - x) ** 2 + (gy - y) ** 2) / (2.0 * (rr * 1.2) ** 2)
        m = np.exp(-d2) * a
        sub = out[ay0:ay1, ax0:ax1]
        sub *= (1.0 - m[..., None])


def draw_text(layer_bbox, t):
    """타이핑되는 생각풍선 문구를 별도 캔버스에 렌더."""
    x0, y0, x1, y1 = layer_bbox
    cw, ch = x1 - x0, y1 - y0
    img = Image.new("RGB", (cw, ch), (255, 255, 255))
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(FONT_B, 52)
    full = LINE1 + LINE2
    n = len(full)
    p = clip01((t - TYPING_T0) / (TYPING_T1 - TYPING_T0))
    shown = int(math.floor(p * (n + 0.001)))
    cx = BUBBLE_C[0]
    y1c = BUBBLE_C[1] - 44
    y2c = BUBBLE_C[1] + 46
    total1 = f.getlength(LINE1)
    total2 = f.getlength(LINE2)
    rnd = random.Random(5)
    off = [rnd.uniform(-0.9, 0.9) for _ in range(64)]
    def put(s, x_start, yc, start_index, upto):
        for i, ch in enumerate(s):
            gi = start_index + i
            if gi > upto:
                return
            if ch == " ":
                continue
            alph = 235 if gi < upto else 175
            d.text((x_start + f.getlength(s[:i]) - x0, yc - y0 + off[gi % 64]),
                   ch, font=f, fill=(34, 34, 38, alph), anchor="mm")
    put(LINE1, cx - total1 / 2, y1c, 0, shown - 1)
    put(LINE2, cx - total2 / 2, y2c, len(LINE1), shown - 1)
    # 커서
    if 0 <= shown < n and t < TYPING_T1 + 0.6:
        blink = 0.5 + 0.5 * math.sin(2 * math.pi * 2.2 * (t - TYPING_T0))
        if t > TYPING_T1 - 0.05 or blink > 0.25:
            if shown <= len(LINE1):
                xc = cx - total1 / 2 + f.getlength(LINE1[:shown]) + 3
                yc = y1c
            else:
                xc = cx - total2 / 2 + f.getlength(LINE2[:shown - len(LINE1)]) + 3
                yc = y2c
            d.line([(xc - x0 - 4, yc - y0 - 24), (xc - x0 + 1, yc - y0 + 26)],
                   fill=(58, 58, 62, 150), width=2)
    img = img.filter(ImageFilter.GaussianBlur(0.35))
    a = 1.0 - np.asarray(img.convert("L"), np.float32) / 255.0
    return a


def make_paper():
    rng = np.random.default_rng(11)
    small = rng.normal(size=(H // 48 + 2, W // 48 + 2)).astype(np.float32)
    mott = np.asarray(
        Image.fromarray(np.clip(small * 26 + 128, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC),
        np.float32)
    mott = (mott - 128.0) / 255.0
    fine = rng.normal(size=(H, W)).astype(np.float32)
    fin = np.asarray(
        Image.fromarray(np.clip(fine * 38 + 128, 0, 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(0.6)), np.float32)
    fin = (fin - 128.0) / 255.0
    v = 1.0 + mott * 0.060 + fin * 0.055
    return np.clip(PAPER[None, None, :] * v[..., None], 0, 1).astype(np.float32)


def make_vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = (xx / W - 0.5) * 2.0
    ny = (yy / H - 0.5) * 2.0
    r = np.sqrt(nx * nx * 0.82 + ny * ny)
    return np.clip(1.0 - 0.15 * np.clip((r - 0.58) / 0.72, 0, 1) ** 1.4, 0, 1).astype(np.float32)


def make_grain(n=24):
    """반해상도 그레인(업스케일) — 프레임 간 변화가 커서 압축률이 나빠지므로 부드럽게."""
    rng = np.random.default_rng(99)
    hw, hh = W // 2, H // 2
    tiles = []
    for _ in range(n):
        a = rng.integers(0, 256, size=(hh, hw), dtype=np.uint8)
        tiles.append(np.asarray(Image.fromarray(a).resize((W, H), Image.BILINEAR),
                                np.float32))
    return tiles


def build_dust():
    rng = random.Random(7)
    return [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.25, 1.1),
             rng.uniform(18, 70), rng.uniform(0, 6.28), rng.uniform(1.0, 2.6),
             rng.uniform(0.05, 0.16)) for _ in range(46)]


# ------------------------------------------------------------------ render ---
class Scene:
    def __init__(self):
        self.L = build_scene()
        self.paper = make_paper()
        self.vig = make_vignette()
        self.grain = make_grain()
        self.dust = build_dust()
        self.text_bbox = (int(BUBBLE_C[0] - BUBBLE_RX * 0.86) - 4,
                          int(BUBBLE_C[1] - BUBBLE_RY * 0.80) - 4,
                          int(BUBBLE_C[0] + BUBBLE_RX * 0.86) + 4,
                          int(BUBBLE_C[1] + BUBBLE_RY * 0.80) + 4)
        self.typing_started = False

    def render(self, t):
        out = self.paper.copy()
        L = self.L
        # 1) 수동 그리기 레이어
        for name in ("bg", "bench"):
            ly = L[name]
            a = layer_canvas(ly, t)
            if a is not None:
                composite(out, a, ly.bbox)
        for name, sh in (("legs", legs_bob), ("torso", person_bob),
                         ("head", head_bob), ("arm", person_bob)):
            ly = L[name]
            a = layer_canvas(ly, t)
            if a is None:
                continue
            dx, dy = sh(t)
            if abs(dx) > 0.01 or abs(dy) > 0.01:
                a = shift2d(a, dy, dx)
            composite(out, a, ly.bbox)
        # 2) 생각풍선
        for i in range(len(TRAILS)):
            ly = L["trail%d" % i]
            m = trail_motion(i)(t)
            if m is None:
                continue
            s, dx, dy = m
            pop_composite(out, ly, s, TRAILS[i][0][0], TRAILS[i][0][1], dx, dy)
        cl = L["cloud"]
        m = cloud_motion(t)
        if m is not None:
            s, dx, dy = m
            pop_composite(out, cl, s, BUBBLE_C[0], BUBBLE_C[1], dx, dy)
            # 3) 문구
            if t > TYPING_T0 - 0.35:
                ta = draw_text(self.text_bbox, t)
                x0, y0, x1, y1 = self.text_bbox
                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    ta = shift2d(ta, dy, dx)
                composite(out, ta, self.text_bbox)
        # 4) 먼지 + 종이 질감 + 그레인 + 비네팅
        draw_dust(out, self.dust, t)
        out *= self.vig[..., None]
        g = (self.grain[int(t * FPS / 2) % len(self.grain)] - 128.0) / 255.0 * 0.045
        out += g[..., None]
        # 5) 페이드 인/아웃
        f = 1.0
        if t < 0.7:
            f = smoothstep(t / 0.7)
        if t > DUR - 0.9:
            f = min(f, 1.0 - smoothstep((t - (DUR - 0.9)) / 0.9))
        if f < 1.0:
            out = out * f + PAPER[None, None, :] * (1.0 - f)
        return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "stills"
    sc = Scene()
    if mode == "stills":
        times = [float(x) for x in sys.argv[2:]] or [2.5, 5.0, 7.2, 9.0, 13.0]
        for t in times:
            img = Image.fromarray(sc.render(t))
            p = os.path.join(PREV, "t%05.2f.png" % t)
            img.save(p)
            print("wrote", p)
        return
    dst = os.path.join(OUT, "charcoal_bench.mp4")
    n = int(round(DUR * FPS))
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
         "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow",
         "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(n):
        t = i / FPS
        p.stdin.write(sc.render(t).tobytes())
        if i % 30 == 0:
            print("frame %d/%d  t=%.2f" % (i, n, t), flush=True)
    p.stdin.close()
    p.wait()
    poster = Image.fromarray(sc.render(12.2))
    poster.save(os.path.join(OUT, "poster.png"))
    print("done", dst)


if __name__ == "__main__":
    main()
