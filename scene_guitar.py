#!/usr/bin/env python3
"""씬: 클래식 기타를 연주하는 사람.

지오메트리·레이어·모션 정의만 담는다. 프레임 합성·질감·인코딩은 engine.py.
계약은 engine.py 모듈 독스트링 참고.
"""
import math
import random

from engine import (catmull, stroke, hatch, fill_ink, ellipse_poly, blob,
                    Layer, smoothstep)

# ------------------------------------------------------------------ pose ---
# 좌향 프로파일로 앉아 클래식 기타를 연주하는 자세
P_DY = 0


def _dy(pts, d=P_DY):
    return [(x, y + d) for x, y in pts]


def rot_pts(pts, c, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa,
             c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


# 머리 (bench 씬과 같은 좌향 프로파일 골격)
HEAD_C = (1000.0, 336.0)
HEAD_TILT = -11.0
HAIR = rot_pts(_dy([(956, 338), (960, 318), (976, 308), (998, 304), (1020, 308), (1038, 320),
                    (1050, 338), (1054, 362), (1048, 390), (1036, 412), (1024, 424),
                    (1014, 440), (1004, 424), (994, 438), (988, 418),
                    (992, 398), (984, 386), (974, 376), (964, 380), (956, 362), (948, 372),
                    (946, 354), (952, 346)]), HEAD_C, HEAD_TILT)
FACE = rot_pts(_dy([(952, 344), (944, 358), (940, 368), (928, 382), (936, 390), (932, 398),
                    (936, 404), (938, 416), (946, 428), (960, 438), (978, 444)]), HEAD_C, HEAD_TILT)
NECKLINE = _dy([(996, 438), (1010, 452), (1022, 468)])

# 몸통 (왼쪽으로 살짝 숙인 상체)
BACK = _dy([(1122, 706), (1098, 620), (1054, 548), (1012, 486), (998, 466)])
CHEST = _dy([(986, 710), (958, 650), (926, 578), (910, 512), (902, 482)])
SHOULDER = (944, 470)
HIP = (1092, 710)

# 다리 (앉아서 무릎을 앞으로 굽힘) — 좌향
OUT_LEG = [(1096, 706), (980, 730), (884, 754), (852, 760), (838, 812), (830, 884)]
IN_LEG = [(1090, 756), (986, 780), (900, 800), (878, 802), (872, 820), (868, 878)]
FAR_LEG = [(1104, 688), (994, 704), (902, 722), (868, 724), (856, 770), (850, 844)]
SHOE = [(866, 876), (840, 892), (788, 898), (770, 886), (790, 872), (828, 864)]

# 생각풍선 (우상단 — 기타 넥과 겹치지 않게)
BUBBLE_C = (1500.0, 296.0)
BUBBLE_RX, BUBBLE_RY = 344.0, 190.0
TRAILS = [((1090, 300), 27.0), ((1194, 274), 18.0), ((1298, 256), 11.0)]

TYPING_T0, TYPING_T1 = 7.9, 10.4
TEXT_LINES = ("줄 하나를 누르면", "오래된 노래가 흐른다")
TEXT_SIZE = 60
TEXT_DY = (-58, 60)

DESC = "클래식 기타를 연주하는 사람"
DUR = 13.8
OUT_MP4 = "charcoal_guitar.mp4"
POSTER_PNG = "guitar_poster.png"
POSTER_T = 12.2

# 기타 로컬 좌표계: 넥이 -y(위)를 향한다. G_ANG만큼 회전해 좌상단으로 눕힌다.
G_ORG = (1000.0, 695.0)
G_ANG = -40.0


def gpts(pts):
    return [(x + G_ORG[0], y + G_ORG[1]) for x, y in rot_pts(pts, (0.0, 0.0), G_ANG)]


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


def guitar_bob(t):
    dx, dy = person_bob(t)
    return (dx * 0.9, dy * 0.9)  # 기타도 호흡에 맞춰 미세하게 흔들림


def strum_bob(t):
    # 오른손 스트럼: 호흡 + 미세한 상하 왕복
    dx, dy = person_bob(t)
    w = smoothstep((t - 5.6) / 1.6)
    return (dx, dy + w * 2.4 * math.sin(2 * math.pi * 0.75 * (t - 5.6)))


# 합성 순서 + 프레임 내 이동 함수
ORDER = (("bg", None), ("stand", None), ("stool", None), ("legs", None),
         ("torso", person_bob), ("head", head_bob), ("guitar", guitar_bob),
         ("arm_l", person_bob), ("arm_r", strum_bob))


# ------------------------------------------------------------ scene builder --
def build_scene():
    L = {}

    def new(name, **kw):
        ly = Layer(name, kw.pop("seed", abs(hash(name)) % 9999), **kw)
        L[name] = ly
        return ly

    # ---- 배경: 바닥선 + 바닥 해칭 + 뮤직 스탠드
    bg = new("bg", seed=11, reveal=(0.7, 2.0), direction=(1.0, 0.25), blur=0.6)
    d = bg.d
    stroke(d, [(90, 820), (600, 812), (1150, 818), (1830, 810)],
           value=(120, 120, 124), alpha=110, width=1.6, wob=1.4, seed=3, passes=1, skip=0.16)
    hatch(d, [[(20, 826), (1900, 818), (1900, 1080), (20, 1080)]],
          angle=2, spacing=26, value=(150, 150, 154), alpha=70, seed=5,
          dash=(10, 34, 22), width=1.3)
    hatch(d, [[(0, 828), (1920, 820), (1920, 1080), (0, 1080)]],
          angle=3, spacing=23, value=(135, 135, 139), alpha=85, seed=6,
          dash=(14, 40, 26), width=1.4)
    rnd = random.Random(21)
    for i in range(120):
        x = rnd.uniform(10, 1910)
        y = rnd.uniform(830, 1060)
        ln = rnd.uniform(6, 26)
        stroke(d, [(x, y), (x + ln, y + rnd.uniform(-3, 3))], value=(120, 120, 124),
               alpha=rnd.randint(50, 105), width=1.3, wob=0.8,
               seed=200 + i, passes=1, skip=0.0, step=6)

    # ---- 뮤직 스탠드 (왼쪽 배경 소품)
    stand = new("stand", seed=14, reveal=(1.4, 2.4), direction=(0.2, 1.0), blur=0.55, gain=1.05)
    d = stand.d
    stroke(d, [(360, 906), (362, 636)], value=(58, 58, 62), alpha=190, width=2.6, wob=1.2, seed=15)
    for (x0, y0, x1, y1) in ((362, 862, 304, 906), (362, 862, 420, 906)):
        stroke(d, [(x0, y0), (x1, y1)], value=(70, 70, 74), alpha=165, width=2.0,
               wob=1.1, seed=int(x0), passes=1)
    board = [(276, 566), (446, 540), (458, 600), (288, 626)]
    stroke(d, board + [board[0]], value=(52, 52, 56), alpha=205, width=2.6, wob=1.2, seed=16)
    hatch(d, [board], angle=8, spacing=9, value=(128, 128, 132), alpha=70, seed=17,
          dash=(12, 28, 10), width=1.3)
    for k in range(3):  # 오선 느낌의 가로선
        yy = 574 + k * 11
        stroke(d, [(292, yy), (446, yy - 12)], value=(96, 96, 100), alpha=120, width=1.1,
               wob=0.4, seed=40 + k, passes=1, step=4)

    # ---- 스툴 (좌식 받침)
    stool = new("stool", seed=12, reveal=(1.8, 2.7), direction=(1.0, 0.15), blur=0.55, gain=1.08)
    d = stool.d
    A, B, T = 950, 1230, 716
    stroke(d, [(A, T), (B, T)], value=(44, 44, 48), alpha=222, width=3.2, wob=1.8, seed=13)
    stroke(d, [(A, T), (A, T + 26)], value=(58, 58, 62), alpha=185, width=2.2, wob=1.3, seed=14)
    stroke(d, [(B, T - 2), (B, T + 26)], value=(74, 74, 78), alpha=165, width=2.0, wob=1.3, seed=15)
    stroke(d, [(A, T + 26), (B - 4, T + 28)], value=(80, 80, 84), alpha=150, width=1.9, wob=1.4, seed=16)
    fill_ink(d, [[(A, T), (B, T), (B, T + 26), (A, T + 26)]], angle=84,
             value=(104, 104, 108), alpha=55, seed=17, spacing=4.4, width=2.0)
    for (xa, xb, s) in ((984, 1010, 21), (1170, 1196, 22)):
        stroke(d, [(xa, T + 26), (xb - 6, 902)], value=(48, 48, 52), alpha=200, width=2.4,
               wob=1.5, seed=s)
        stroke(d, [(xb, T + 26), (xa + 8, 902)], value=(70, 70, 74), alpha=160, width=1.9,
               wob=1.5, seed=s + 1)
    stroke(d, [(1000, 812), (1186, 820)], value=(88, 88, 92), alpha=150, width=1.7,
           wob=1.4, seed=25)

    # ---- 다리 (먼 다리 → 가까운 다리) — 좌향
    legs = new("legs", seed=31, reveal=(2.6, 3.4), direction=(1.0, 0.4), blur=0.5, gain=1.14)
    d = legs.d
    stroke(d, catmull(FAR_LEG, 8), value=(126, 126, 130), alpha=140, width=2.1, wob=1.5,
           seed=32, passes=1)
    stroke(d, SHOE + [SHOE[0]], value=(46, 46, 50), alpha=220, width=3.0, wob=1.3, seed=41)
    fill_ink(d, [SHOE + [SHOE[0]]], angle=-24, value=(88, 88, 92), alpha=95, seed=87,
             spacing=3.6, width=2.2)
    stroke(d, catmull(OUT_LEG, 8), value=(42, 42, 46), alpha=222, width=3.2, wob=1.6, seed=34)
    stroke(d, catmull(IN_LEG, 8), value=(76, 76, 80), alpha=170, width=2.0, wob=1.3, seed=35, passes=1)
    trouser = catmull(OUT_LEG, 8) + list(reversed(catmull(IN_LEG, 8)))
    hatch(d, [trouser], angle=78, spacing=8, value=(118, 118, 122), alpha=95, seed=39,
          dash=(16, 34, 8), width=1.5)
    stroke(d, [(868, 878), (884, 876)], value=(80, 80, 84), alpha=160, width=1.8,
           wob=0.6, seed=36, passes=1, step=4)
    # 앉은 자세: 엉덩이가 받침에 닿는 곡선
    stroke(d, catmull([(1096, 706), (1122, 720), (1132, 748), (1100, 760), (1046, 760)], 8),
           value=(58, 58, 62), alpha=195, width=2.4, wob=1.5, seed=38)

    # ---- 몸통 (상체)
    torso = new("torso", seed=41, reveal=(3.3, 4.2), direction=(0.15, 1.0), blur=0.5, gain=1.16)
    d = torso.d
    stroke(d, catmull(BACK, 12), value=(40, 40, 44), alpha=218, width=3.0, wob=1.9, seed=42)
    stroke(d, catmull(CHEST, 10), value=(58, 58, 62), alpha=190, width=2.3, wob=1.7, seed=43)
    stroke(d, catmull([(1022, 468), (1046, 462), (1066, 476), (1078, 494)], 8),
           value=(48, 48, 52), alpha=205, width=2.3, wob=1.4, seed=44)
    hatch(d, [BACK + list(reversed(CHEST))], angle=-40, spacing=8,
          value=(120, 120, 124), alpha=100, seed=46, dash=(16, 34, 8), width=1.5)
    hatch(d, [BACK + list(reversed(CHEST))], angle=34, spacing=13,
          value=(132, 132, 136), alpha=70, seed=47, dash=(14, 30, 10), width=1.3)
    stroke(d, catmull(_dy([(1064, 512), (1090, 566), (1120, 626), (1148, 676)]), 6),
           value=(112, 112, 116), alpha=110, width=1.6, wob=1.1, seed=91, passes=1)

    # ---- 머리 (bench 씬과 동일한 좌향 프로파일)
    head = new("head", seed=51, reveal=(4.0, 4.8), direction=(0.25, 1.0), blur=0.45, gain=1.16)
    d = head.d
    HP = lambda pts: rot_pts(_dy(pts), HEAD_C, HEAD_TILT)
    stroke(d, catmull(FACE, 9), value=(40, 40, 44), alpha=225, width=3.0, wob=1.2, seed=54)
    fill_ink(d, [HAIR], angle=72, value=(58, 58, 62), alpha=120, seed=61, spacing=3.0, width=2.4)
    fill_ink(d, [HAIR], angle=12, value=(72, 72, 76), alpha=55, seed=62, spacing=4.4, width=2.0)
    for (pts, sd) in (([(986, 318), (1002, 332), (1014, 352), (1020, 376)], 66),
                      ([(966, 326), (980, 342), (990, 362), (994, 384)], 67)):
        stroke(d, catmull(HP(pts), 6), value=(104, 104, 108), alpha=110, width=1.6,
               wob=0.9, seed=sd, passes=1, step=5)
    stroke(d, HAIR + [HAIR[0]], value=(40, 40, 44), alpha=225, width=3.0, wob=1.3, seed=52)
    stroke(d, catmull(HP([(994, 394), (1004, 396), (1006, 408), (998, 414), (992, 408)]), 6),
           value=(64, 64, 68), alpha=185, width=2.0, wob=0.9, seed=63, passes=1)
    stroke(d, HP([(1000, 398), (1003, 407)]), value=(92, 92, 96), alpha=135, width=1.5,
           wob=0.5, seed=64, passes=1, step=4)
    stroke(d, HP([(948, 366), (964, 362)]), value=(58, 58, 62), alpha=195, width=2.2,
           wob=0.8, seed=57)
    stroke(d, catmull(HP([(948, 386), (956, 392), (964, 386)]), 5), value=(48, 48, 52),
           alpha=215, width=2.3, wob=0.7, seed=58)
    stroke(d, HP([(964, 386), (968, 384)]), value=(48, 48, 52), alpha=180, width=1.6,
           wob=0.4, seed=68, passes=1, step=4)
    stroke(d, HP([(938, 404), (947, 405)]), value=(84, 84, 88), alpha=165, width=1.7,
           wob=0.5, seed=59, passes=1, step=4)
    stroke(d, catmull(NECKLINE, 6), value=(54, 54, 58), alpha=195, width=2.2, wob=1.0, seed=55)
    hatch(d, [HP([(948, 408), (968, 420), (964, 432), (946, 424)])], angle=44, spacing=6,
          value=(122, 122, 126), alpha=70, seed=56, dash=(10, 20, 8), width=1.2)

    # ---- 클래식 기타 (몸통 → 넥 → 줄)
    guitar = new("guitar", seed=101, reveal=(4.4, 5.2), direction=(-0.4, 1.0), blur=0.45, gain=1.14)
    d = guitar.d
    HALF = [(0, -185), (60, -164), (72, -132), (68, -92), (60, -52), (56, -16),
            (62, 22), (92, 58), (98, 104), (92, 146), (64, 182), (30, 196), (0, 200)]
    BODY = HALF + [(-x, y) for (x, y) in reversed(HALF[1:-1])]
    BODY = gpts(BODY)
    NECK = gpts([(-11, -185), (-9, -466), (9, -466), (11, -185)])
    HEADSTOCK = gpts([(-9, -466), (-17, -528), (-12, -548), (12, -548), (17, -528), (9, -466)])
    # 몸통: 옅은 단색 + 나뭇결 해칭
    fill_ink(d, [BODY], angle=38, value=(196, 196, 200), alpha=70, seed=102, spacing=3.6, width=2.0)
    hatch(d, [BODY], angle=38, spacing=11, value=(132, 132, 136), alpha=72, seed=103,
          dash=(18, 44, 12), width=1.3)
    stroke(d, BODY + [BODY[0]], value=(38, 38, 42), alpha=228, width=3.2, wob=1.4, seed=104)
    # 넥
    fill_ink(d, [NECK], angle=30, value=(150, 150, 154), alpha=70, seed=105, spacing=3.6, width=2.0)
    stroke(d, NECK + [NECK[0]], value=(46, 46, 50), alpha=215, width=2.4, wob=1.0, seed=106)
    for fy in range(-450, -204, 27):   # 프렛
        stroke(d, gpts([(-9, fy), (9, fy)]), value=(96, 96, 100), alpha=140, width=1.3,
               wob=0.4, seed=1000 + fy, passes=1, step=4)
    # 헤드스톡 + 줄감개
    fill_ink(d, [HEADSTOCK], angle=60, value=(52, 52, 56), alpha=150, seed=107, spacing=3.0, width=2.2)
    stroke(d, HEADSTOCK + [HEADSTOCK[0]], value=(40, 40, 44), alpha=225, width=2.6, wob=1.0, seed=108)
    for sx in (-8, 8):
        for sy in (-506, -526):
            stroke(d, gpts([(sx, sy), (sx * 2.4, sy)]), value=(70, 70, 74), alpha=170,
                   width=1.8, wob=0.5, seed=abs(sx) * 100 + abs(sy), passes=1, step=4)
    # 브리지
    BRIDGE = gpts([(-38, 104), (38, 104), (32, 134), (-32, 134)])
    stroke(d, BRIDGE + [BRIDGE[0]], value=(46, 46, 50), alpha=210, width=2.2, wob=0.9, seed=109)
    fill_ink(d, [BRIDGE], angle=8, value=(80, 80, 84), alpha=90, seed=110, spacing=3.2, width=2.0)
    # 사운드홀 + 로제트
    hole = gpts(ellipse_poly(0, -4, 40, 42, n=28, rot=-0.1))
    fill_ink(d, [hole], angle=62, value=(44, 44, 48), alpha=170, seed=111, spacing=2.6, width=2.4)
    stroke(d, hole + [hole[0]], value=(34, 34, 38), alpha=225, width=2.6, wob=0.8, seed=112)
    ring = gpts(ellipse_poly(0, -4, 53, 55, n=28, rot=-0.1))
    stroke(d, ring + [ring[0]], value=(110, 110, 114), alpha=130, width=1.5, wob=0.6, seed=113, passes=1)
    # 줄 (6현)
    for o in (-14, -8, -3, 3, 8, 14):
        stroke(d, gpts([(o * 0.34, -450), (o, 96)]), value=(90, 90, 94), alpha=150,
               width=1.0, wob=0.3, seed=600 + o, passes=1, step=5)

    # ---- 왼팔 (넥 짚는 손)
    arm_l = new("arm_l", seed=71, reveal=(4.9, 5.5), direction=(0.6, 0.8), blur=0.5, gain=1.18)
    d = arm_l.d
    L_UP = [(952, 468), (996, 520), (1002, 574), (988, 602)]
    L_UP_IN = [(916, 486), (954, 536), (956, 588), (942, 608)]
    sleeve_l = catmull(L_UP, 8) + list(reversed(catmull(L_UP_IN, 8)))
    hatch(d, [sleeve_l], angle=-58, spacing=8, value=(126, 126, 130), alpha=78, seed=74,
          dash=(14, 32, 8), width=1.4)
    stroke(d, catmull(L_UP, 8), value=(44, 44, 48), alpha=215, width=2.8, wob=1.5, seed=72)
    stroke(d, catmull(L_UP_IN, 8), value=(78, 78, 82), alpha=160, width=1.9, wob=1.3, seed=73, passes=1)
    L_FO = [(988, 602), (934, 600), (862, 548), (806, 470)]
    L_FO_IN = [(942, 608), (902, 610), (842, 566), (788, 498)]
    fore_l = catmull(L_FO, 8) + list(reversed(catmull(L_FO_IN, 8)))
    hatch(d, [fore_l], angle=-20, spacing=8, value=(128, 128, 132), alpha=68, seed=76,
          dash=(12, 30, 8), width=1.3)
    stroke(d, catmull(L_FO, 8), value=(42, 42, 46), alpha=215, width=2.6, wob=1.4, seed=77)
    stroke(d, catmull(L_FO_IN, 8), value=(84, 84, 88), alpha=150, width=1.8, wob=1.2, seed=78, passes=1)
    # 짚는 손 (넥 위)
    HAND_L = [(832, 462), (802, 452), (776, 466), (782, 490), (812, 496), (834, 482)]
    stroke(d, HAND_L + [HAND_L[0]], value=(40, 40, 44), alpha=215, width=2.5, wob=1.0, seed=79)
    hatch(d, [HAND_L], angle=32, spacing=6, value=(104, 104, 108), alpha=85, seed=82,
          dash=(8, 18, 6), width=1.2)

    # ---- 오른팔 (스트럼하는 손)
    arm_r = new("arm_r", seed=81, reveal=(5.0, 5.5), direction=(0.6, 0.8), blur=0.5, gain=1.18)
    d = arm_r.d
    R_UP = [(988, 470), (1046, 536), (1074, 600), (1072, 650)]
    R_UP_IN = [(952, 488), (1012, 550), (1042, 610), (1042, 660)]
    sleeve_r = catmull(R_UP, 8) + list(reversed(catmull(R_UP_IN, 8)))
    hatch(d, [sleeve_r], angle=-52, spacing=8, value=(126, 126, 130), alpha=78, seed=84,
          dash=(14, 32, 8), width=1.4)
    stroke(d, catmull(R_UP, 8), value=(44, 44, 48), alpha=215, width=2.8, wob=1.5, seed=85)
    stroke(d, catmull(R_UP_IN, 8), value=(78, 78, 82), alpha=160, width=1.9, wob=1.3, seed=86, passes=1)
    R_FO = [(1072, 650), (1066, 700), (1042, 730), (1012, 736)]
    R_FO_IN = [(1042, 660), (1040, 704), (1018, 730), (994, 730)]
    fore_r = catmull(R_FO, 8) + list(reversed(catmull(R_FO_IN, 8)))
    hatch(d, [fore_r], angle=-16, spacing=8, value=(128, 128, 132), alpha=68, seed=88,
          dash=(12, 30, 8), width=1.3)
    stroke(d, catmull(R_FO, 8), value=(42, 42, 46), alpha=215, width=2.6, wob=1.4, seed=89)
    stroke(d, catmull(R_FO_IN, 8), value=(84, 84, 88), alpha=150, width=1.8, wob=1.2, seed=90, passes=1)
    # 스트럼하는 손
    HAND_R = [(1032, 706), (1010, 694), (984, 700), (980, 722), (1004, 732), (1030, 722)]
    stroke(d, HAND_R + [HAND_R[0]], value=(40, 40, 44), alpha=215, width=2.5, wob=1.0, seed=91)
    hatch(d, [HAND_R], angle=-30, spacing=6, value=(104, 104, 108), alpha=85, seed=92,
          dash=(8, 18, 6), width=1.2)

    # ---- 생각풍선 꼬리 + 구름
    for i, (c, r) in enumerate(TRAILS):
        ly = new("trail%d" % i, seed=121 + i)
        q = ellipse_poly(c[0], c[1], r, r * 0.94, n=22, rot=0.3 * i)
        stroke(ly.d, q + [q[0]], value=(48, 48, 52), alpha=200, width=2.2, wob=1.0,
               seed=121 + i, passes=2)

    cloud = new("cloud", seed=131, blur=0.5)
    q = blob(BUBBLE_C[0], BUBBLE_C[1], BUBBLE_RX, BUBBLE_RY, bumps=9, seed=132)
    stroke(cloud.d, q + [q[0]], value=(40, 40, 44), alpha=222, width=3.4, wob=1.6,
           seed=133, passes=2, skip=0.03, step=6)
    q2 = blob(BUBBLE_C[0], BUBBLE_C[1] + 4, BUBBLE_RX * 0.985, BUBBLE_RY * 0.985,
              bumps=9, seed=132)
    stroke(cloud.d, q2 + [q2[0]], value=(120, 120, 124), alpha=110, width=1.8, wob=1.4,
           seed=134, passes=1, skip=0.12, step=6)

    for ly in L.values():
        ly.prep()
    return L
