#!/usr/bin/env python3
"""공용 드로잉 엔진 — 모노톤 목탄 질감 만화풍 모션그래픽.

씬(scene_*.py)이 지오메트리·레이어·모션을 제공하면 이 모듈이 프레임 합성·
질감·후처리·인코딩을 담당한다. 씬 추가 방법은 README "씬 추가하기" 참고.

씬 모듈 계약 (scene_<id>.py, 파일명의 <id>가 --scene 선택자):
  DESC                                     --list 표시용 설명
  DUR, OUT_MP4, POSTER_PNG, POSTER_T       길이(초)와 출력 파일명, 포스터 시각
  BUBBLE_C, BUBBLE_RX, BUBBLE_RY, TRAILS   생각풍선 중심·반경·꼬리 위치
  TYPING_T0, TYPING_T1                     문구 타이핑 시작·종료 시각
  TEXT_LINES, TEXT_SIZE, TEXT_DY           풍선 문구, 폰트 크기, 줄별 y 오프셋
  build_scene() -> {"이름": Layer, ...}    레이어 사전
  ORDER = (("bg", None), ("legs", legs_bob), ...)  합성 순서 + 프레임 내 이동 함수

공용 말풍선 모션: trail_pop(i, t0) / cloud_pop(t0) — 팝 오버슈트 + 부유.
"""
import glob
import importlib
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 30

INK = np.array([46, 46, 50], np.float32) / 255.0
PAPER = np.array([240, 240, 238], np.float32) / 255.0

FONT_B = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_R = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PREV = os.path.join(HERE, "preview")

# 말풍선 연출 타이밍 — 단독 컷(make_motion)과 대사 시퀀스(make_dialogue) 공용
TRAIL_T0 = 6.05      # 첫 꼬리 팝(단독 컷 기준; 리빌 종료 5.55s + 여유)
TRAIL_GAP = 0.30     # 꼬리 풍선 간 간격
T_CLOUD = 0.70       # 꼬리 시작 → 구름 팝
T_TYPE_DELAY = 0.90  # 구름 팝 → 타이핑 시작
T_FADE = 0.35        # 말풍선 페이드아웃
T_NEXT_GAP = 0.15    # 페이드 끝 → 다음 꼬리
INTRO_MARGIN = 0.5   # 마지막 리빌 종료 → 첫 꼬리 팝 여유
OUTRO = 1.2


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


# ------------------------------------------------------------ bubble pops ---
def trail_pop(i, t0):
    """꼬리 풍선 i번째 팝: (스케일, dx, dy) 또는 None(t0 전)."""
    def f(t):
        if t < t0:
            return None
        p = clip01((t - t0) / 0.42)
        s = ease_out_back(p) if p < 1 else 1.0
        s *= 1.0 + 0.06 * math.sin(2 * math.pi * 0.45 * (t - t0) - i * 0.8)
        dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
        return (s, 0.0, dy)
    return f


def cloud_pop(t0):
    """생각풍선 구름 팝: (스케일, dx, dy) 또는 None(t0 전)."""
    def f(t):
        if t < t0:
            return None
        p = clip01((t - t0) / 0.62)
        s = ease_out_back(p) if p < 1 else 1.0
        s *= 1.0 + 0.010 * math.sin(2 * math.pi * 0.45 * (t - t0))
        dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
        dx = 1.4 * math.sin(2 * math.pi * 0.28 * (t - t0))
        return (s, dx, dy)
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


def text_bbox(bubble_c, rx, ry):
    """풍선 안 텍스트 영역(bubble 너비 86%·높이 80%)."""
    return (int(bubble_c[0] - rx * 0.86) - 4,
            int(bubble_c[1] - ry * 0.80) - 4,
            int(bubble_c[0] + rx * 0.86) + 4,
            int(bubble_c[1] + ry * 0.80) + 4)


def draw_text(bbox, t, lines, size, dys, t0, t1, center):
    """단독 컷용 타이핑 문구(줄 수 무관). 대사 시퀀스용은 make_dialogue.draw_bubble_text."""
    x0, y0, x1, y1 = bbox
    img = Image.new("RGB", (x1 - x0, y1 - y0), (255, 255, 255))
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(FONT_B, size)
    n = sum(len(s) for s in lines)
    p = clip01((t - t0) / (t1 - t0))
    shown = int(math.floor(p * (n + 0.001)))
    cx, cy = center
    rnd = random.Random(5)
    off = [rnd.uniform(-0.9, 0.9) for _ in range(64)]
    gi = 0
    for k, s in enumerate(lines):
        yc = cy + dys[k]
        xs = cx - f.getlength(s) / 2.0
        for i, ch in enumerate(s):
            if gi > shown - 1:
                break
            if ch != " ":
                alph = 235 if gi < shown - 1 else 175
                d.text((xs + f.getlength(s[:i]) - x0, yc - y0 + off[gi % 64]),
                       ch, font=f, fill=(34, 34, 38, alph), anchor="mm")
            gi += 1
    # 커서
    if 0 <= shown < n and t < t1 + 0.6:
        cum = 0
        for k, s in enumerate(lines):
            if shown <= cum + len(s):
                xs = cx - f.getlength(s) / 2.0
                xc = xs + f.getlength(s[:shown - cum]) + 3
                yc = cy + dys[k]
                blink = 0.5 + 0.5 * math.sin(2 * math.pi * 2.2 * (t - t0))
                if t > t1 - 0.05 or blink > 0.25:
                    d.line([(xc - x0 - 4, yc - y0 - 24), (xc - x0 + 1, yc - y0 + 26)],
                           fill=(58, 58, 62, 150), width=2)
                break
            cum += len(s)
    img = img.filter(ImageFilter.GaussianBlur(0.35))
    a = 1.0 - np.asarray(img.convert("L"), np.float32) / 255.0
    return a


# ------------------------------------------------------------- textures ---
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
    """단독 컷(고정 문구) 렌더러. 씬 모듈 하나를 받아 프레임을 만든다."""

    def __init__(self, scene):
        self.s = scene
        self.L = scene.build_scene()
        self.paper = make_paper()
        self.vig = make_vignette()
        self.grain = make_grain()
        self.dust = build_dust()
        self.text_bbox = text_bbox(scene.BUBBLE_C, scene.BUBBLE_RX, scene.BUBBLE_RY)

    def render(self, t):
        out = self.paper.copy()
        L = self.L
        s = self.s
        # 1) 레이어: 합성 순서는 씬의 ORDER, 이동 함수가 있으면 프레임 내에서 이동
        for name, sh in s.ORDER:
            ly = L[name]
            a = layer_canvas(ly, t)
            if a is None:
                continue
            if sh is not None:
                dx, dy = sh(t)
                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    a = shift2d(a, dy, dx)
            composite(out, a, ly.bbox)
        # 2) 생각풍선: 꼬리 → 구름 → 문구
        for i in range(len(s.TRAILS)):
            ly = L["trail%d" % i]
            m = trail_pop(i, TRAIL_T0 + i * TRAIL_GAP)(t)
            if m is None:
                continue
            sc, dx, dy = m
            pop_composite(out, ly, sc, s.TRAILS[i][0][0], s.TRAILS[i][0][1], dx, dy)
        cl = L["cloud"]
        m = cloud_pop(TRAIL_T0 + T_CLOUD)(t)
        if m is not None:
            sc, dx, dy = m
            pop_composite(out, cl, sc, s.BUBBLE_C[0], s.BUBBLE_C[1], dx, dy)
            if t > s.TYPING_T0 - 0.35:
                ta = draw_text(self.text_bbox, t, s.TEXT_LINES, s.TEXT_SIZE,
                               s.TEXT_DY, s.TYPING_T0, s.TYPING_T1, s.BUBBLE_C)
                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    ta = shift2d(ta, dy, dx)
                composite(out, ta, self.text_bbox)
        # 3) 먼지 + 비네팅 + 그레인
        draw_dust(out, self.dust, t)
        out *= self.vig[..., None]
        g = (self.grain[int(t * FPS / 2) % len(self.grain)] - 128.0) / 255.0 * 0.045
        out += g[..., None]
        # 4) 페이드 인/아웃
        f = 1.0
        if t < 0.7:
            f = smoothstep(t / 0.7)
        if t > s.DUR - 0.9:
            f = min(f, 1.0 - smoothstep((t - (s.DUR - 0.9)) / 0.9))
        if f < 1.0:
            out = out * f + PAPER[None, None, :] * (1.0 - f)
        return (np.clip(out, 0, 1) * 255).astype(np.uint8)


# ---------------------------------------------------------------- encode ---
def render_mp4(render_fn, dur, dst, fps=FPS):
    """render_fn(t) → (H,W,3) uint8 프레임을 ffmpeg로 mp4 인코딩한다."""
    n = int(round(dur * fps))
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
         "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow",
         "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(n):
        t = i / fps
        p.stdin.write(render_fn(t).tobytes())
        if i % 30 == 0:
            print("frame %d/%d  t=%.2f" % (i, n, t), flush=True)
    p.stdin.close()
    return p.wait()


# ------------------------------------------------------------ scene discovery ---
def find_scenes():
    """charcoal-bench 안의 scene_*.py를 {id: 모듈}로 수집한다."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    mods = {}
    for path in sorted(glob.glob(os.path.join(HERE, "scene_*.py"))):
        base = os.path.basename(path)[:-3]
        mods[base[len("scene_"):]] = importlib.import_module(base)
    return mods


def load_scene(name):
    mods = find_scenes()
    if name not in mods:
        raise SystemExit("알 수 없는 씬 '%s' (사용 가능: %s)"
                         % (name, ", ".join(sorted(mods)) or "없음"))
    return mods[name]
