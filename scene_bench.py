#!/usr/bin/env python3
"""씬: 벤치에 앉아 생각하는 사람 (기본 씬).

지오메트리·레이어·모션 정의만 담는다. 프레임 합성·질감·인코딩은 engine.py.
계약은 engine.py 모듈 독스트링 참고.
"""
import math
import random

from PIL import Image

from engine import (W, H, catmull, stroke, hatch, fill_ink, ellipse_poly, blob,
                    Layer, smoothstep)

HORIZON = 636

# 인물 지오메트리
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
FAR_LEG = [(1220, 660), (962, 692), (952, 872), (892, 894)]
FOOT = [(898, 864), (894, 898), (830, 898), (818, 886), (838, 878), (896, 862)]
# 인물·벤치 그룹을 우하단으로 밀어 말풍선이 화면을 크게 차지하게 한다
SX, SY = 260, 140

# 생각풍선
BUBBLE_C = (540.0, 340.0)
BUBBLE_RX, BUBBLE_RY = 470.0, 300.0
TRAILS = [((1150, 470), 30.0), ((1096, 432), 20.0), ((1050, 398), 12.0)]

TYPING_T0, TYPING_T1 = 7.9, 10.4
TEXT_LINES = ("10년의 계획에서", "2년이 흘러가고 있다")
TEXT_SIZE = 64
TEXT_DY = (-58, 60)

DESC = "벤치에 앉아 생각하는 사람"
DUR = 13.8
OUT_MP4 = "charcoal_bench.mp4"
POSTER_PNG = "poster.png"
POSTER_T = 12.2


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


# 합성 순서 + 프레임 내 이동 함수 (엔진 렌더 루프가 이 순서를 따른다)
ORDER = (("bg", None), ("bench", None), ("legs", legs_bob), ("torso", person_bob),
         ("head", head_bob), ("arm", person_bob))


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
    stroke(d, [(190, 902), (198, 800), (194, 700), (198, 672)], value=(84, 84, 88), alpha=200,
           width=3.6, wob=1.4, seed=71)
    stroke(d, [(214, 900), (208, 800), (204, 706), (206, 678)], value=(118, 118, 122), alpha=120,
           width=2.0, wob=1.2, seed=72, passes=1)
    can = blob(200, 620, 80, 60, bumps=8, seed=73)
    stroke(d, can + [can[0]], value=(72, 72, 76), alpha=190, width=2.4, wob=1.4,
           seed=74, passes=2, step=6)
    hatch(d, [can], angle=-35, spacing=12, value=(130, 130, 134), alpha=60, seed=75,
          dash=(14, 30, 12), width=1.4)
    bsh = blob(1832, 824, 66, 26, bumps=6, seed=76, amp=0.12)
    stroke(d, bsh + [bsh[0]], value=(84, 84, 88), alpha=170, width=2.0, wob=1.2,
           seed=77, passes=1, step=5)
    hatch(d, [bsh], angle=15, spacing=9, value=(124, 124, 128), alpha=70, seed=78,
          dash=(10, 24, 10), width=1.2)
    for (gx, gy) in ((1790, 846), (1842, 852), (1872, 844)):
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
        stroke(ly.d, q + [q[0]], value=(48, 48, 52), alpha=200, width=2.2, wob=1.0,
               seed=81 + i, passes=2)
    cloud = new("cloud", seed=91, blur=0.5)
    q = blob(BUBBLE_C[0], BUBBLE_C[1], BUBBLE_RX, BUBBLE_RY, bumps=9, seed=92)
    stroke(cloud.d, q + [q[0]], value=(40, 40, 44), alpha=222, width=3.4, wob=1.6,
           seed=93, passes=2, skip=0.03, step=6)
    q2 = blob(BUBBLE_C[0], BUBBLE_C[1] + 4, BUBBLE_RX * 0.985, BUBBLE_RY * 0.985,
              bumps=9, seed=92)
    stroke(cloud.d, q2 + [q2[0]], value=(120, 120, 124), alpha=110, width=1.8, wob=1.4,
           seed=94, passes=1, skip=0.12, step=6)

    # 인물·벤치 그룹을 (SX, SY)만큼 우하단으로 이동 (좌표 개별 수정 없이 그룹 이동)
    if SX or SY:
        for name in ("bench", "legs", "torso", "head", "arm"):
            ly = L[name]
            moved = Image.new("RGB", (W, H), (255, 255, 255))
            moved.paste(ly.img, (SX, SY))
            ly.img = moved

    for ly in L.values():
        ly.prep()
    return L
