#!/usr/bin/env python3
"""대사 txt → 말풍선 시퀀스 모션그래픽 생성기.

txt의 비어있지 않은 줄 1줄 = 생각풍선 1개. 꼬리 팝 → 구름 팝 → 타이핑 →
hold → 페이드아웃을 줄 수만큼 반복한다. 화면·질감·인물 모션은
make_motion.py를 import해 그대로 재사용한다.

  python3 make_dialogue.py sample_dialogue.txt                    # out/dialogue_bench.mp4
  python3 make_dialogue.py sample_dialogue.txt stills 8 12 20     # 미리보기 PNG
  python3 make_dialogue.py my.txt -o out/x.mp4 --cps 12 --hold 1.2
"""
import argparse
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import make_motion as mm
from make_motion import (BUBBLE_C, BUBBLE_RX, BUBBLE_RY, TRAILS, W, H, FPS,
                         FONT_B, OUT, PREV, clip01, smoothstep, composite,
                         shift2d, layer_canvas, pop_composite, draw_dust,
                         make_paper, make_vignette, make_grain, build_dust)

TEXT_MAXW = 2 * BUBBLE_RX * 0.84   # 풍선 안 텍스트 최대 폭
TEXT_MAXH = 2 * BUBBLE_RY * 0.80   # 풍선 안 텍스트 최대 높이

T_TRAIL_GAP = 0.30     # 꼬리 풍선 간 간격
T_CLOUD = 0.70         # 꼬리 시작 → 구름 팝
T_TYPE_DELAY = 0.90    # 구름 팝 → 타이핑 시작
T_FADE = 0.35          # 말풍선 페이드아웃
T_NEXT_GAP = 0.15      # 페이드 끝 → 다음 꼬리
INTRO_MARGIN = 0.5     # 마지막 리빌 종료 → 첫 꼬리 팝 여유 (make_motion 수정 추적용)
OUTRO = 1.2


# ------------------------------------------------------------- bubble pops --
def trail_pop(idx, t0):
    def f(t):
        if t < t0:
            return None
        p = clip01((t - t0) / 0.42)
        s = mm.ease_out_back(p) if p < 1 else 1.0
        s *= 1.0 + 0.06 * math.sin(2 * math.pi * 0.45 * (t - t0) - idx * 0.8)
        dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
        return (s, 0.0, dy)
    return f


def cloud_pop(t0):
    def f(t):
        if t < t0:
            return None
        p = clip01((t - t0) / 0.62)
        s = mm.ease_out_back(p) if p < 1 else 1.0
        s *= 1.0 + 0.010 * math.sin(2 * math.pi * 0.45 * (t - t0))
        dy = 3.2 * math.sin(2 * math.pi * 0.45 * (t - t0) - 0.6)
        dx = 1.4 * math.sin(2 * math.pi * 0.28 * (t - t0))
        return (s, dx, dy)
    return f


# ------------------------------------------------------------------- text ---
def wrap_text(s, font, maxw):
    """글자 단위 그리디 줄바꿈(공백 우선). 한글 무공수 문장도 처리."""
    lines = []
    cur = ""
    for ch in s:
        if cur and font.getlength(cur + ch) > maxw:
            cut = cur.rfind(" ")
            if cut > 0:
                lines.append(cur[:cut].rstrip())
                cur = (cur[cut + 1:] + ch).lstrip()
            else:
                lines.append(cur)
                cur = ch if ch != " " else ""
        else:
            cur += ch
    lines.append(cur.rstrip())
    return [ln for ln in lines if ln] or [""]


def fit_text(s):
    """풍선 안에 맞는 폰트 크기·줄바꿈 결정."""
    for size in (64, 56, 48, 40, 32, 26, 22):
        f = ImageFont.truetype(FONT_B, size)
        lines = wrap_text(s, f, TEXT_MAXW)
        lh = size * 1.42
        if len(lines) * lh <= TEXT_MAXH:
            return f, lines, lh
    f = ImageFont.truetype(FONT_B, 22)
    lines = wrap_text(s, f, TEXT_MAXW)
    lh = 22 * 1.42
    maxn = max(1, int(TEXT_MAXH / lh))
    if len(lines) > maxn:
        lines = lines[:maxn]
        lines[-1] = lines[-1][:-1] + "…"
    return f, lines, lh


def draw_bubble_text(bbox, font, lines, lh, t0, t1, t, fade):
    """타이핑되는 풍선 문구를 별도 캔버스에 렌더(alpha 배열 반환)."""
    x0, y0, x1, y1 = bbox
    img = Image.new("RGB", (x1 - x0, y1 - y0), (255, 255, 255))
    d = ImageDraw.Draw(img, "RGBA")
    n = sum(len(s) for s in lines)
    p = clip01((t - t0) / max(1e-6, t1 - t0))
    shown = int(math.floor(p * (n + 0.001)))
    cx = BUBBLE_C[0]
    y_first = BUBBLE_C[1] - (len(lines) - 1) * lh / 2.0
    rnd = random.Random(5)
    off = [rnd.uniform(-0.9, 0.9) for _ in range(64)]
    gi = 0
    for k, s in enumerate(lines):
        yc = y_first + k * lh
        xs = cx - font.getlength(s) / 2.0
        for i, ch in enumerate(s):
            if gi > shown - 1:
                break
            if ch != " ":
                alph = int(235 * fade) if gi < shown - 1 else int(175 * fade)
                d.text((xs + font.getlength(s[:i]) - x0, yc - y0 + off[gi % 64]),
                       ch, font=font, fill=(34, 34, 38, alph), anchor="mm")
            gi += 1
    # 커서
    if shown < n and t < t1 + 0.6:
        cum = 0
        for k, s in enumerate(lines):
            if shown <= cum + len(s):
                xs = cx - font.getlength(s) / 2.0
                xc = xs + font.getlength(s[:shown - cum]) + 3 - x0
                yc = y_first + k * lh - y0
                blink = 0.5 + 0.5 * math.sin(2 * math.pi * 2.2 * (t - t0))
                if t > t1 - 0.05 or blink > 0.25:
                    d.line([(xc - 4, yc - 28), (xc + 1, yc + 30)],
                           fill=(58, 58, 62, int(150 * fade)), width=2)
                break
            cum += len(s)
    img = img.filter(ImageFilter.GaussianBlur(0.35))
    a = 1.0 - np.asarray(img.convert("L"), np.float32) / 255.0
    return a * fade


# ---------------------------------------------------------------- schedule --
def build_schedule(lines, hold, cps, intro_end):
    segs = []
    t = intro_end
    for s in lines:
        type_dur = max(0.6, len(s) / cps)
        seg = {"text": s,
               "t_trail": t,
               "t_cloud": t + T_CLOUD,
               "t_type0": t + T_TYPE_DELAY,
               "t_type1": t + T_TYPE_DELAY + type_dur,
               "t_end": t + T_TYPE_DELAY + type_dur + hold + T_FADE}
        segs.append(seg)
        t = seg["t_end"] + T_NEXT_GAP
    return segs, segs[-1]["t_end"] + OUTRO


def read_lines(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        raw = fh.read().splitlines()
    return [ln.strip() for ln in raw if ln.strip()]


# ------------------------------------------------------------------ scene ---
class DialogueScene:
    def __init__(self, lines, hold=1.4, cps=10.0):
        self.L = mm.build_scene()
        # 첫 말풍선 시각 = make_motion 리빌이 모두 끝나는 시각 + 여유
        reveal_ends = [ly.reveal[1] for ly in self.L.values() if ly.reveal]
        self.intro_end = (max(reveal_ends) if reveal_ends else 5.55) + INTRO_MARGIN
        self.paper = make_paper()
        self.vig = make_vignette()
        self.grain = make_grain()
        self.dust = build_dust()
        self.segs, self.dur = build_schedule(lines, hold, cps, self.intro_end)
        for seg in self.segs:
            seg["font"], seg["wlines"], seg["lh"] = fit_text(seg["text"])
        self.text_bbox = (int(BUBBLE_C[0] - BUBBLE_RX * 0.86) - 4,
                          int(BUBBLE_C[1] - BUBBLE_RY * 0.80) - 4,
                          int(BUBBLE_C[0] + BUBBLE_RX * 0.86) + 4,
                          int(BUBBLE_C[1] + BUBBLE_RY * 0.80) + 4)

    def active(self, t):
        for seg in self.segs:
            if seg["t_trail"] <= t < seg["t_end"]:
                return seg
        return None

    def render(self, t):
        out = self.paper.copy()
        L = self.L
        # 1) 수동 그리기 레이어
        for name in ("bg", "bench"):
            ly = L[name]
            a = layer_canvas(ly, t)
            if a is not None:
                composite(out, a, ly.bbox)
        for name, sh in (("legs", mm.legs_bob), ("torso", mm.person_bob),
                         ("head", mm.head_bob), ("arm", mm.person_bob)):
            ly = L[name]
            a = layer_canvas(ly, t)
            if a is None:
                continue
            dx, dy = sh(t)
            if abs(dx) > 0.01 or abs(dy) > 0.01:
                a = shift2d(a, dy, dx)
            composite(out, a, ly.bbox)
        # 2) 활성 대사 말풍선 (꼬리 → 구름 → 문구)
        seg = self.active(t)
        if seg:
            fade = 1.0 - smoothstep((t - (seg["t_end"] - T_FADE)) / T_FADE)
            for k in range(len(TRAILS)):
                ly = L["trail%d" % k]
                m = trail_pop(k, seg["t_trail"] + k * T_TRAIL_GAP)(t)
                if m is None:
                    continue
                s, dx, dy = m
                pop_composite(out, ly, s, TRAILS[k][0][0], TRAILS[k][0][1], dx, dy, fade=fade)
            m = cloud_pop(seg["t_cloud"])(t)
            if m is not None:
                s, dx, dy = m
                pop_composite(out, L["cloud"], s, BUBBLE_C[0], BUBBLE_C[1], dx, dy, fade=fade)
                if t > seg["t_type0"] - 0.05:
                    ta = draw_bubble_text(self.text_bbox, seg["font"], seg["wlines"],
                                          seg["lh"], seg["t_type0"], seg["t_type1"], t, fade)
                    if abs(dx) > 0.01 or abs(dy) > 0.01:
                        ta = shift2d(ta, dy, dx)
                    composite(out, ta, self.text_bbox)
        # 3) 먼지 + 종이 질감 + 그레인 + 비네팅
        draw_dust(out, self.dust, t)
        out *= self.vig[..., None]
        g = (self.grain[int(t * FPS / 2) % len(self.grain)] - 128.0) / 255.0 * 0.045
        out += g[..., None]
        # 4) 페이드 인/아웃
        f = 1.0
        if t < 0.7:
            f = smoothstep(t / 0.7)
        if t > self.dur - 0.9:
            f = min(f, 1.0 - smoothstep((t - (self.dur - 0.9)) / 0.9))
        if f < 1.0:
            out = out * f + mm.PAPER[None, None, :] * (1.0 - f)
        return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description="대사 txt → 말풍선 시퀀스 mp4")
    ap.add_argument("script", help="대사 txt 파일 (줄 1줄 = 말풍선 1개)")
    ap.add_argument("mode", nargs="?", default="render", choices=["render", "stills"])
    ap.add_argument("times", nargs="*", type=float, help="stills 모드 시각(초)")
    ap.add_argument("-o", "--out", default=None, help="출력 mp4 경로(기본 out/dialogue_bench.mp4)")
    ap.add_argument("--hold", type=float, default=1.4, help="타이핑 끝 후 유지(초, 기본 1.4)")
    ap.add_argument("--cps", type=float, default=10.0, help="타이핑 속도(자/초, 기본 10)")
    ap.add_argument("--poster-t", type=float, default=None, help="포스터 시각(초)")
    args = ap.parse_args()

    lines = read_lines(args.script)
    if not lines:
        sys.exit("대사가 없습니다: %s" % args.script)
    sc = DialogueScene(lines, hold=args.hold, cps=args.cps)
    print("lines=%d  duration=%.2fs" % (len(lines), sc.dur))
    for i, seg in enumerate(sc.segs):
        print("  [%d] pop %.2f  type %.2f-%.2f  end %.2f  (%d자)" % (
            i, seg["t_trail"], seg["t_type0"], seg["t_type1"], seg["t_end"], len(seg["text"])))

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    if args.mode == "stills":
        times = args.times or [sc.intro_end + 2.0, sc.dur * 0.5, sc.dur - 1.0]
        for tt in times:
            img = Image.fromarray(sc.render(tt))
            pth = os.path.join(PREV, "dt%05.2f.png" % tt)
            img.save(pth)
            print("wrote", pth)
        return

    dst = args.out or os.path.join(OUT, "dialogue_bench.mp4")
    n = int(round(sc.dur * FPS))
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
    poster_t = args.poster_t
    if poster_t is None:
        poster_t = sc.segs[-1]["t_type1"] + min(0.7, args.hold * 0.5)
    poster_t = min(poster_t, sc.dur - 1.0)
    Image.fromarray(sc.render(poster_t)).save(os.path.join(OUT, "dialogue_poster.png"))
    print("done", dst)


if __name__ == "__main__":
    main()
