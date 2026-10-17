#!/usr/bin/env python3
"""모노톤 목탄 질감 만화풍 모션그래픽 생성기 (풀밭 독서 버전).

풀밭에 무릎을 세우고 앉아 책을 읽는 사람 + 생각풍선("종이 위 작은 활자 속에 / 끝없는 우주가 담겨 있다").
기존 make_motion.py의 드로잉 엔진을 바탕으로 지오메트리(자세, 소품, 배경)를 재구성했습니다.

실행 방법:
  python3 make_motion2.py stills 1.0 3.0 6.0 9.0 12.5   # 미리보기 PNG 생성
  python3 make_motion2.py render                        # out/charcoal_reading.mp4 생성
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

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PREV = os.path.join(HERE, "preview")

# ---------------------------------------------------------------- geometry ---
# 풀밭 배경 지오메트리
GROUND = 880
HORIZON = 680

LINE1 = "종이 위 작은 활자 속에"
LINE2 = "끝없는 우주가 담겨 있다"
TYPING_T0, TYPING_T1 = 7.9, 10.4

P_DY = 0

def _dy(pts, d=P_DY):
    return [(x, y + d) for x, y in pts]

def rot_pts(pts, c, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa,
             c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]

# 캐릭터 자세 재구성 (무릎 세우고 책 읽는 자세)
# 몸통: 앞으로 살짝 숙인 형태
BACK = _dy([(1120, 850), (1160, 720), (1150, 580), (1090, 480), (1060, 460)])
CHEST = _dy([(1000, 820), (1030, 680), (1030, 560), (1040, 500), (1050, 480)])
SHOULDER = (1060, 500)

# 머리: 밑으로 많이 숙임 (책을 보는 각도)
HEAD_C = (980, 410)
HEAD_TILT = -35.0  

# 머리카락 및 얼굴 (기존 형상 유지, 각도와 위치만 변경)
HAIR = rot_pts(_dy([(956, 338), (960, 318), (976, 308), (998, 304), (1020, 308), (1038, 320),
                    (1050, 338), (1054, 362), (1048, 390), (1036, 412), (1024, 424),
                    (1014, 440), (1004, 424), (994, 438), (988, 418),
                    (992, 398), (984, 386), (974, 376), (964, 380), (956, 362), (948, 372),
                    (946, 354), (952, 346)]), HEAD_C, HEAD_TILT)
FACE = rot_pts(_dy([(952, 344), (944, 358), (940, 368), (928, 382), (936, 390), (932, 398),
                    (936, 404), (938, 416), (946, 428), (960, 438), (978, 444)]), HEAD_C, HEAD_TILT)
NECKLINE = _dy([(1010, 450), (1030, 470)])

# 다리: 무릎을 세운 형태 (삼각형 구도)
HIP_PT = (1100, 830)
KNEE_PT = (830, 610)
FOOT_PT = (740, 870)

# 생각풍선 위치 (책 읽는 캐릭터 위쪽)
BUBBLE_C = (480.0, 240.0)
BUBBLE_RX, BUBBLE_RY = 340.0, 168.0
TRAILS = [((880, 380), 22.0), ((820, 340), 13.0), ((780, 310), 7.0)]

def clip01(v): return 0.0 if v < 0 else (1.0 if v > 1 else v)
def smoothstep(p): p = clip01(p); return p * p * (3 - 2 * p)
def ease_out_back(p):
    c1, c3 = 1.70158, 2.70158
    p -= 1.0
    return 1 + c3 * p * p * p + c1 * p * p

# ------------------------------------------------------------ stroke utils ---
# (기존 make_motion.py의 드로잉 유틸리티 함수 그대로 사용)
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
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)))
    out.append((float(p[-2][0]), float(p[-2][1])))
    return out

def wobble(pts, amp=1.7, seed=0):
    n = len(pts)
    if n < 2 or amp <= 0: return list(pts)
    rng = np.random.default_rng(seed)
    f1, f2 = rng.uniform(0.7, 1.5), rng.uniform(2.0, 3.6)
    p1, p2 = rng.uniform(0, 6.283), rng.uniform(0, 6.283)
    a1, a2 = rng.uniform(0.7, 1.3), rng.uniform(0.35, 0.85)
    idx = np.arange(n)
    off = amp * (a1 * np.sin(2 * np.pi * f1 * idx / n + p1) + a2 * np.sin(2 * np.pi * f2 * idx / n + p2))
    off = off + rng.normal(0, amp * 0.10, n)
    res = []
    for i, (x, y) in enumerate(pts):
        i0, i1 = max(0, i - 1), min(n - 1, i + 1)
        dx, dy = pts[i1][0] - pts[i0][0], pts[i1][1] - pts[i0][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        res.append((x + nx * off[i], y + ny * off[i]))
    return res

def stroke(d, pts, value=(48, 48, 52), alpha=205, width=2.2, wob=1.7, seed=0, passes=2, skip=0.05, step=4.0):
    if len(pts) < 2: return
    base = densify(pts, step=step)
    v = tuple(int(c) for c in value)
    for pi in range(passes):
        rnd = random.Random(seed * 977 + pi * 31)
        jp = wobble(base, amp=wob * (1.0 + 0.55 * pi), seed=seed * 131 + pi)
        w0 = max(1.0, width * (1.0 + (pi - 0.5) * 0.30))
        a0 = alpha * (1.0 - 0.20 * pi)
        for i in range(len(jp) - 1):
            if rnd.random() < skip: continue
            aa = int(max(0, min(255, a0 * rnd.uniform(0.80, 1.05))))
            ww = int(round(w0 * rnd.uniform(0.85, 1.25)))
            d.line([jp[i], jp[i + 1]], fill=v + (aa,), width=max(1, ww))

def hatch(d, polys, angle, spacing, value=(66, 66, 70), alpha=135, seed=0, dash=(16, 26, 11), wob=1.0, width=1.5):
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, y0 = max(0, int(min(xs)) - 2), max(0, int(min(ys)) - 2)
    x1, y1 = min(W, int(max(xs)) + 3), min(H, int(max(ys)) + 3)
    if x1 - x0 < 3 or y1 - y0 < 3: return
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    md = ImageDraw.Draw(m)
    for poly in polys: md.polygon([(px - x0, py - y0) for px, py in poly], fill=255)
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
                    ok = False; break
            else:
                a, b = (0 - o) / u, (lim - o) / u
                if a > b: a, b = b, a
                lo, hi = max(lo, a), min(hi, b)
        if not ok or hi - lo < 4: continue
        step = 3.0
        ns = int((hi - lo) / step) + 1
        on = []
        for k in range(ns + 1):
            t = lo + k * step
            xi, yi = int(ox + ux * t), int(oy + uy * t)
            on.append(0 <= xi < w and 0 <= yi < h and mask[yi, xi])
        k = 0
        while k < len(on):
            if not on[k]: k += 1; continue
            j = k
            while j < len(on) and on[j]: j += 1
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
                            (ox + ux * te + jx + x0, oy + uy * te + jy + y0)], fill=v + (aa,), width=max(1, int(round(rnd.uniform(width * 0.7, width * 1.35)))))
                t_cur = te + gl
            k = j

def fill_ink(d, polys, angle, value=(70, 70, 74), alpha=90, seed=0, spacing=3.4, width=2.2, wob=1.0):
    hatch(d, polys, angle, spacing, value=value, alpha=alpha, seed=seed, dash=(26, 64, 0), wob=wob, width=width)

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
    def __init__(self, name, seed, reveal=None, direction=(1, 0), opacity=1.0, shift=None, blur=0.5, ink=INK, gain=1.0):
        self.name = name
        self.img = Image.new("RGB", (W, H), (255, 255, 255))
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.seed = seed
        self.reveal = reveal
        self.direction = direction
        self.opacity = opacity
        self.blur = blur
        self.ink = ink
        self.gain = gain
        self.ready = False

    def prep(self):
        if self.ready: return
        if self.blur > 0: self.img = self.img.filter(ImageFilter.GaussianBlur(self.blur))
        if self.gain != 1.0:
            g = self.gain
            self.img = self.img.point(lambda v: int(max(0, min(255, 255 - (255 - v) * g))))
        a = 1.0 - np.asarray(self.img.convert("L"), np.float32) / 255.0
        ys, xs = np.nonzero(a > 0.015)
        if len(ys) == 0:
            self.bbox = (0, 0, 1, 1); self.alpha = a; self.order = None; self.ready = True; return
        x0 = max(0, int(xs.min()) - 3)
        y0 = max(0, int(ys.min()) - 3)
        x1 = min(W, int(xs.max()) + 4)
        y1 = min(H, int(ys.max()) + 4)
        self.bbox = (x0, y0, x1, y1)
        self.alpha = a
        if self.reveal:
            yy, xx = np.mgrid[0:(y1-y0), 0:(x1-x0)].astype(np.float32)
            dx, dy = self.direction
            nrm = math.hypot(dx, dy) or 1.0
            proj = (xx / max(1, x1-x0-1)) * dx / nrm + (yy / max(1, y1-y0-1)) * dy / nrm
            proj = (proj - proj.min()) / (float(proj.max() - proj.min()) + 1e-6)
            rng = np.random.default_rng(self.seed)
            nz = rng.normal(size=(max(2, (y1-y0) // 30), max(2, (x1-x0) // 30))).astype(np.float32)
            nz = (nz - nz.min()) / (float(nz.max() - nz.min()) + 1e-6)
            nz = np.asarray(Image.fromarray((nz * 255).astype(np.uint8)).resize(((x1-x0), (y1-y0)), Image.BILINEAR), np.float32) / 255.0
            self.order = np.clip(proj * 0.90 + nz * 0.10, 0, 1).astype(np.float32)
        else:
            self.order = None
        self.ready = True

def shift2d(a, dy, dx):
    if abs(dy) < 1e-4 and abs(dx) < 1e-4: return a
    iy, ix = int(math.floor(dy)), int(math.floor(dx))
    fy, fx = dy - iy, dx - ix
    r = lambda k, m: np.roll(np.roll(a, k, 0), m, 1)
    return (r(iy, ix) * (1 - fy) * (1 - fx) + r(iy + 1, ix) * fy * (1 - fx) + r(iy, ix + 1) * (1 - fy) * fx + r(iy + 1, ix + 1) * fy * fx)

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

    # ---- 배경 (언덕 형태의 풀밭)
    bg = new("bg", seed=11, reveal=(0.7, 2.1), direction=(1.0, -0.2), blur=0.6)
    d = bg.d
    
    # 완만한 언덕 라인
    hill = catmull([(-50, 750), (400, 780), (960, 850), (1500, 820), (1950, 760)], 10)
    stroke(d, hill, value=(120, 120, 124), alpha=130, width=2.0, wob=1.5, seed=3)
    
    # 바닥 전체 해칭 (잔디 느낌)
    hatch(d, [[(0, 760), (1920, 740), (1920, 1080), (0, 1080)]], angle=15, spacing=18, value=(140, 140, 144), alpha=80, seed=5, dash=(10, 30, 15), width=1.4)
    hatch(d, [[(0, 800), (1920, 780), (1920, 1080), (0, 1080)]], angle=-10, spacing=22, value=(130, 130, 134), alpha=70, seed=6, dash=(12, 35, 20), width=1.3)
    
    # 흩뿌려진 잔디들
    rnd = random.Random(21)
    for i in range(150):
        x = rnd.uniform(10, 1910)
        y = rnd.uniform(780, 1060)
        ln = rnd.uniform(10, 30)
        angle = rnd.uniform(-1.8, -1.2)
        stroke(d, [(x, y), (x + ln * math.cos(angle), y + ln * math.sin(angle))], value=(100, 100, 104), alpha=rnd.randint(80, 140), width=1.5, wob=0.8, seed=200 + i, passes=1, step=6)

    # 멀리 있는 나무
    tree = blob(1600, 680, 120, 180, bumps=6, seed=76, amp=0.15)
    stroke(d, tree + [tree[0]], value=(84, 84, 88), alpha=170, width=2.0, wob=1.2, seed=77, passes=2, step=5)
    hatch(d, [tree], angle=25, spacing=10, value=(110, 110, 114), alpha=80, seed=78, dash=(10, 24, 10), width=1.2)
    stroke(d, [(1590, 810), (1600, 880)], value=(70, 70, 74), alpha=200, width=4.0, wob=1.0, seed=80)

    # ---- 사람 (다리 → 몸통 → 머리 → 팔 → 책)
    legs = new("legs", seed=31, reveal=(1.8, 2.7), direction=(1.0, 0.2), blur=0.5, gain=1.16)
    d = legs.d
    
    # 먼 쪽 다리 (살짝 보임)
    FAR_LEG = [(1050, 840), (950, 780), (880, 700), (840, 840)]
    stroke(d, catmull(FAR_LEG, 8), value=(124, 124, 128), alpha=145, width=2.2, wob=1.6, seed=32, passes=1)
    
    # 가까운 다리 (무릎 굽힘)
    OUT_LEG = [HIP_PT, (980, 850), (900, 810), KNEE_PT, (790, 720), FOOT_PT]
    IN_LEG = [(1100, 810), (970, 750), (870, 650), KNEE_PT, (830, 740), (790, 850)]
    trouser = catmull(OUT_LEG, 8) + list(reversed(catmull(IN_LEG, 8)))
    
    hatch(d, [trouser], angle=70, spacing=8, value=(118, 118, 122), alpha=95, seed=39, dash=(16, 34, 8), width=1.5)
    stroke(d, catmull(OUT_LEG, 8), value=(42, 42, 46), alpha=222, width=3.2, wob=1.6, seed=34)
    stroke(d, catmull(IN_LEG, 8), value=(76, 76, 80), alpha=170, width=2.0, wob=1.3, seed=35, passes=1)
    
    # 신발
    SHOE = [(740, 870), (720, 890), (660, 895), (650, 880), (700, 860)]
    stroke(d, SHOE + [SHOE[0]], value=(46, 46, 50), alpha=222, width=3.0, wob=1.3, seed=41)
    fill_ink(d, [SHOE + [SHOE[0]]], angle=-24, value=(88, 88, 92), alpha=95, seed=87, spacing=3.6, width=2.2)

    torso = new("torso", seed=41, reveal=(2.5, 3.4), direction=(0.15, 1.0), blur=0.5, gain=1.16)
    d = torso.d
    stroke(d, catmull(BACK, 12), value=(40, 40, 44), alpha=218, width=3.0, wob=1.9, seed=42)
    stroke(d, catmull(CHEST, 10), value=(58, 58, 62), alpha=190, width=2.3, wob=1.7, seed=43)
    hatch(d, [BACK + list(reversed(CHEST))], angle=-35, spacing=8, value=(120, 120, 124), alpha=100, seed=46, dash=(16, 34, 8), width=1.5)
    hatch(d, [BACK + list(reversed(CHEST))], angle=45, spacing=13, value=(132, 132, 136), alpha=70, seed=47, dash=(14, 30, 10), width=1.3)
    
    # 옷 주름
    stroke(d, catmull([(1090, 480), (1050, 550), (1030, 680)], 6), value=(112, 112, 116), alpha=110, width=1.6, wob=1.1, seed=91, passes=1)

    head = new("head", seed=51, reveal=(3.2, 3.9), direction=(0.25, 1.0), blur=0.45, gain=1.16)
    d = head.d
    HP = lambda pts: rot_pts(_dy(pts), HEAD_C, HEAD_TILT)
    stroke(d, catmull(FACE, 9), value=(40, 40, 44), alpha=225, width=3.0, wob=1.2, seed=54)
    fill_ink(d, [HAIR], angle=72, value=(58, 58, 62), alpha=120, seed=61, spacing=3.0, width=2.4)
    fill_ink(d, [HAIR], angle=12, value=(72, 72, 76), alpha=55, seed=62, spacing=4.4, width=2.0)
    stroke(d, HAIR + [HAIR[0]], value=(40, 40, 44), alpha=225, width=3.0, wob=1.3, seed=52)
    # 눈 (아래를 향해 감은 형태)
    stroke(d, HP([(950, 380), (965, 385), (975, 380)]), value=(48, 48, 52), alpha=215, width=2.3, wob=0.7, seed=58)
    stroke(d, catmull(NECKLINE, 6), value=(54, 54, 58), alpha=195, width=2.2, wob=1.0, seed=55)

    arm = new("arm", seed=71, reveal=(3.8, 4.5), direction=(0.6, 0.8), blur=0.5, gain=1.20)
    d = arm.d
    # 팔: 무릎 쪽으로 뻗어 책을 잡음
    UP_OUT = [SHOULDER, (1040, 560), (1020, 620)]
    UP_IN = [(1020, 500), (1000, 560), (990, 610)]
    FO_OUT = [(1020, 620), (970, 650), (910, 670)]
    FO_IN = [(990, 610), (950, 630), (890, 650)]
    
    sleeve = catmull(UP_OUT, 8) + list(reversed(catmull(UP_IN, 8)))
    fore = catmull(FO_OUT, 8) + list(reversed(catmull(FO_IN, 8)))
    
    hatch(d, [sleeve], angle=-45, spacing=8, value=(126, 126, 130), alpha=78, seed=74, dash=(14, 32, 8), width=1.4)
    hatch(d, [fore], angle=-20, spacing=8, value=(128, 128, 132), alpha=68, seed=78, dash=(12, 30, 8), width=1.3)
    
    stroke(d, catmull(UP_OUT, 8), value=(44, 44, 48), alpha=215, width=2.8, wob=1.5, seed=72)
    stroke(d, catmull(UP_IN, 8), value=(78, 78, 82), alpha=160, width=1.9, wob=1.3, seed=73, passes=1)
    stroke(d, catmull(FO_OUT, 8), value=(42, 42, 46), alpha=215, width=2.6, wob=1.4, seed=76)
    stroke(d, catmull(FO_IN, 8), value=(84, 84, 88), alpha=150, width=1.8, wob=1.2, seed=77, passes=1)

    # 손
    hand_poly = [(910, 670), (890, 660), (870, 670), (880, 685), (905, 685)]
    stroke(d, hand_poly + [hand_poly[0]], value=(40, 40, 44), alpha=215, width=2.5, wob=1.0, seed=79)

    # ---- 책 (무릎 위에 펼쳐진 상태)
    book = new("book", seed=80, reveal=(4.0, 4.8), direction=(0.0, -1.0), blur=0.4, gain=1.1)
    d = book.d
    
    # 책 중앙선(Spine)과 양쪽 페이지 테두리
    SPINE = [(810, 640), (790, 710)]
    L_PAGE = [(810, 640), (740, 610), (710, 670), (790, 710)]
    R_PAGE = [(810, 640), (900, 620), (890, 690), (790, 710)]
    
    # 책의 하얀 면 (살짝 어둡게 채움)
    fill_ink(d, [L_PAGE, R_PAGE], angle=10, value=(220, 220, 224), alpha=200, seed=82, spacing=2.0, width=2.0)
    
    # 책 외곽선
    stroke(d, L_PAGE, value=(30, 30, 35), alpha=230, width=2.5, wob=0.8, seed=83)
    stroke(d, R_PAGE, value=(30, 30, 35), alpha=230, width=2.5, wob=0.8, seed=84)
    stroke(d, SPINE, value=(50, 50, 55), alpha=200, width=2.0, wob=0.5, seed=85)
    
    # 책 안의 글자(텍스처 느낌의 해칭)
    hatch(d, [L_PAGE], angle=30, spacing=5, value=(100, 100, 105), alpha=120, seed=86, dash=(3, 10, 4), width=1.0)
    hatch(d, [R_PAGE], angle=-10, spacing=5, value=(100, 100, 105), alpha=120, seed=87, dash=(3, 10, 4), width=1.0)

    # ---- 생각풍선 꼬리 + 구름
    for i, (c, r) in enumerate(TRAILS):
        ly = new("trail%d" % i, seed=81 + i)
        q = ellipse_poly(c[0], c[1], r, r * 0.94, n=22, rot=0.3 * i)
        stroke(ly.d, q + [q[0]], value=(48, 48, 52), alpha=200, width=2.0, wob=1.0, seed=81 + i, passes=2)
        
    cloud = new("cloud", seed=91, blur=0.5)
    q = blob(BUBBLE_C[0], BUBBLE_C[1], BUBBLE_RX, BUBBLE_RY, bumps=9, seed=92)
    stroke(cloud.d, q + [q[0]], value=(40, 40, 44), alpha=218, width=2.8, wob=1.6, seed=93, passes=2, skip=0.03, step=6)
    q2 = blob(BUBBLE_C[0], BUBBLE_C[1] + 4, BUBBLE_RX * 0.985, BUBBLE_RY * 0.985, bumps=9, seed=92)
    stroke(cloud.d, q2 + [q2[0]], value=(120, 120, 124), alpha=110, width=1.6, wob=1.4, seed=94, passes=1, skip=0.12, step=6)

    for ly in L.values(): ly.prep()
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

def book_bob(t):
    dx, dy = person_bob(t)
    return (dx * 0.2, dy * 0.8)  # 호흡에 맞춰 책도 미세하게 위아래로 흔들림

def cloud_motion(t):
    t0 = 6.75
    if t < t0: return None
    p = clip01((t - t0) / 0.62)
    s = ease_out_back(p) if p < 1 else 1.0
    s *= 1.0 + 0.010 * math.sin(2 * math.pi * 0.45 * (t - t0))
    dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
    dx = 1.4 * math.sin(2 * math.pi * 0.28 * (t - t0))
    return (s, dx, dy)

def trail_motion(i):
    def f(t):
        t0 = 6.05 + i * 0.30
        if t < t0: return None
        p = clip01((t - t0) / 0.42)
        s = ease_out_back(p) if p < 1 else 1.0
        s *= 1.0 + 0.06 * math.sin(2 * math.pi * 0.45 * (t - t0) - i * 0.8)
        dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
        return (s, 0.0, dy)
    return f

def pop_composite(out, layer, scale, cx, cy, dx=0.0, dy=0.0, fade=1.0):
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
    if abs(dx) > 0.01 or abs(dy) > 0.01: a = shift2d(a, dy, dx)
    composite(out, a, (px0, py0, px1, py1))

def layer_canvas(layer, t):
    x0, y0, x1, y1 = layer.bbox
    if layer.reveal:
        t0, t1 = layer.reveal
        if t <= t0: return None
        r = smoothstep((t - t0) / (t1 - t0))
        thresh = -0.12 + 1.30 * r
        av = np.clip((thresh - layer.order) / 0.09, 0, 1)
        if av.max() <= 0.002: return None
        a = layer.alpha[y0:y1, x0:x1] * av
    else:
        a = layer.alpha[y0:y1, x0:x1]
    if layer.opacity != 1.0: a = a * layer.opacity
    return a

def draw_dust(out, dust, t):
    for (x0, y0, sp, amp, ph, r, a) in dust:
        y = (y0 - sp * t * 26) % (H + 120) - 60
        x = x0 + amp * math.sin(2 * math.pi * 0.12 * t + ph)
        rr = max(1, int(r))
        x0i, y0i = int(x), int(y)
        if not (0 <= x0i < W and 3 <= y0i < H - 3): continue
        k = max(1, rr * 2 + 1)
        ax0, ax1 = max(0, x0i - k), min(W, x0i + k + 2)
        ay0, ay1 = max(0, y0i - k), min(H, y0i + k + 2)
        gy, gx = np.mgrid[ay0:ay1, ax0:ax1].astype(np.float32)
        d2 = ((gx - x) ** 2 + (gy - y) ** 2) / (2.0 * (rr * 1.2) ** 2)
        m = np.exp(-d2) * a
        sub = out[ay0:ay1, ax0:ax1]
        sub *= (1.0 - m[..., None])

def draw_text(layer_bbox, t):
    x0, y0, x1, y1 = layer_bbox
    cw, ch = x1 - x0, y1 - y0
    img = Image.new("RGB", (cw, ch), (255, 255, 255))
    d = ImageDraw.Draw(img, "RGBA")
    try:
        f = ImageFont.truetype(FONT_B, 52)
    except:
        f = ImageFont.load_default()
    full = LINE1 + LINE2
    n = len(full)
    p = clip01((t - TYPING_T0) / (TYPING_T1 - TYPING_T0))
    shown = int(math.floor(p * (n + 0.001)))
    cx = BUBBLE_C[0]
    y1c = BUBBLE_C[1] - 44
    y2c = BUBBLE_C[1] + 46
    
    total1 = f.getlength(LINE1) if hasattr(f, 'getlength') else len(LINE1)*30
    total2 = f.getlength(LINE2) if hasattr(f, 'getlength') else len(LINE2)*30
    
    rnd = random.Random(5)
    off = [rnd.uniform(-0.9, 0.9) for _ in range(64)]
    
    def put(s, x_start, yc, start_index, upto):
        for i, ch in enumerate(s):
            gi = start_index + i
            if gi > upto: return
            if ch == " ": continue
            alph = 235 if gi < upto else 175
            cw = f.getlength(s[:i]) if hasattr(f, 'getlength') else i*30
            d.text((x_start + cw - x0, yc - y0 + off[gi % 64]), ch, font=f, fill=(34, 34, 38, alph), anchor="mm")
            
    put(LINE1, cx - total1 / 2, y1c, 0, shown - 1)
    put(LINE2, cx - total2 / 2, y2c, len(LINE1), shown - 1)
    
    if 0 <= shown < n and t < TYPING_T1 + 0.6:
        blink = 0.5 + 0.5 * math.sin(2 * math.pi * 2.2 * (t - TYPING_T0))
        if t > TYPING_T1 - 0.05 or blink > 0.25:
            if shown <= len(LINE1):
                xc = cx - total1 / 2 + (f.getlength(LINE1[:shown]) if hasattr(f, 'getlength') else shown*30) + 3
                yc = y1c
            else:
                xc = cx - total2 / 2 + (f.getlength(LINE2[:shown - len(LINE1)]) if hasattr(f, 'getlength') else (shown-len(LINE1))*30) + 3
                yc = y2c
            d.line([(xc - x0 - 4, yc - y0 - 24), (xc - x0 + 1, yc - y0 + 26)], fill=(58, 58, 62, 150), width=2)
            
    img = img.filter(ImageFilter.GaussianBlur(0.35))
    a = 1.0 - np.asarray(img.convert("L"), np.float32) / 255.0
    return a

def make_paper():
    rng = np.random.default_rng(11)
    small = rng.normal(size=(H // 48 + 2, W // 48 + 2)).astype(np.float32)
    mott = np.asarray(Image.fromarray(np.clip(small * 26 + 128, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32)
    mott = (mott - 128.0) / 255.0
    fine = rng.normal(size=(H, W)).astype(np.float32)
    fin = np.asarray(Image.fromarray(np.clip(fine * 38 + 128, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), np.float32)
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
    rng = np.random.default_rng(99)
    hw, hh = W // 2, H // 2
    tiles = []
    for _ in range(n):
        a = rng.integers(0, 256, size=(hh, hw), dtype=np.uint8)
        tiles.append(np.asarray(Image.fromarray(a).resize((W, H), Image.BILINEAR), np.float32))
    return tiles

def build_dust():
    rng = random.Random(7)
    return [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.25, 1.1), rng.uniform(18, 70), rng.uniform(0, 6.28), rng.uniform(1.0, 2.6), rng.uniform(0.05, 0.16)) for _ in range(46)]

# ------------------------------------------------------------------ render ---
class Scene:
    def __init__(self):
        self.L = build_scene()
        self.paper = make_paper()
        self.vig = make_vignette()
        self.grain = make_grain()
        self.dust = build_dust()
        self.text_bbox = (int(BUBBLE_C[0] - BUBBLE_RX * 0.86) - 4, int(BUBBLE_C[1] - BUBBLE_RY * 0.80) - 4,
                          int(BUBBLE_C[0] + BUBBLE_RX * 0.86) + 4, int(BUBBLE_C[1] + BUBBLE_RY * 0.80) + 4)

    def render(self, t):
        out = self.paper.copy()
        L = self.L
        
        # 1) 배경 그리기
        bg = L["bg"]
        a = layer_canvas(bg, t)
        if a is not None: composite(out, a, bg.bbox)
            
        # 2) 캐릭터 및 소품(책) 그리기
        for name, sh in (("legs", lambda t: (0,0)), ("torso", person_bob), ("head", head_bob), ("arm", person_bob), ("book", book_bob)):
            ly = L[name]
            a = layer_canvas(ly, t)
            if a is None: continue
            dx, dy = sh(t)
            if abs(dx) > 0.01 or abs(dy) > 0.01: a = shift2d(a, dy, dx)
            composite(out, a, ly.bbox)
            
        # 3) 생각풍선
        for i in range(len(TRAILS)):
            ly = L["trail%d" % i]
            m = trail_motion(i)(t)
            if m is None: continue
            s, dx, dy = m
            pop_composite(out, ly, s, TRAILS[i][0][0], TRAILS[i][0][1], dx, dy)
            
        cl = L["cloud"]
        m = cloud_motion(t)
        if m is not None:
            s, dx, dy = m
            pop_composite(out, cl, s, BUBBLE_C[0], BUBBLE_C[1], dx, dy)
            if t > TYPING_T0 - 0.35:
                ta = draw_text(self.text_bbox, t)
                if abs(dx) > 0.01 or abs(dy) > 0.01: ta = shift2d(ta, dy, dx)
                composite(out, ta, self.text_bbox)
                
        # 4) 후처리 (먼지, 비네팅, 그레인)
        draw_dust(out, self.dust, t)
        out *= self.vig[..., None]
        g = (self.grain[int(t * FPS / 2) % len(self.grain)] - 128.0) / 255.0 * 0.045
        out += g[..., None]
        
        # 5) 페이드 인/아웃
        f = 1.0
        if t < 0.7: f = smoothstep(t / 0.7)
        if t > DUR - 0.9: f = min(f, 1.0 - smoothstep((t - (DUR - 0.9)) / 0.9))
        if f < 1.0: out = out * f + PAPER[None, None, :] * (1.0 - f)
        
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
        
    dst = os.path.join(OUT, "charcoal_reading.mp4")
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
    poster.save(os.path.join(OUT, "reading_poster.png"))
    print("done", dst)

if __name__ == "__main__":
    main()