#!/usr/bin/env python3
"""씬: 풀밭에 무릎 세우고 앉아 책 읽는 사람.

make_motion2.py(단일 스크립트 시절)의 씬 부분을 모듈로 옮긴 것.
지오메트리·레이어·모션 정의만 담는다. 프레임 합성·질감·인코딩은 engine.py.
계약은 engine.py 모듈 독스트링 참고.
"""
import math
import random

from engine import catmull, stroke, hatch, fill_ink, ellipse_poly, blob, Layer, smoothstep

# 캐릭터 자세: 앞으로 살짝 숙여 책을 보는 각도
P_DY = 0


def _dy(pts, d=P_DY):
    return [(x, y + d) for x, y in pts]


def rot_pts(pts, c, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa,
             c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


BACK = _dy([(1120, 850), (1160, 720), (1150, 580), (1090, 480), (1060, 460)])
CHEST = _dy([(1000, 820), (1030, 680), (1030, 560), (1040, 500), (1050, 480)])
SHOULDER = (1060, 500)

# 머리: 밑으로 많이 숙임 (책을 보는 각도)
HEAD_C = (980, 410)
HEAD_TILT = -35.0

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

TYPING_T0, TYPING_T1 = 7.9, 10.4
TEXT_LINES = ("종이 위 작은 활자 속에", "끝없는 우주가 담겨 있다")
TEXT_SIZE = 52
TEXT_DY = (-44, 46)

DESC = "풀밭에 앉아 책 읽는 사람"
DUR = 13.8
OUT_MP4 = "charcoal_reading.mp4"
POSTER_PNG = "reading_poster.png"
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


def book_bob(t):
    dx, dy = person_bob(t)
    return (dx * 0.2, dy * 0.8)  # 호흡에 맞춰 책도 미세하게 위아래로 흔들림


# 합성 순서 + 프레임 내 이동 함수 (다리는 앉은 자세라 고정)
ORDER = (("bg", None), ("legs", None), ("torso", person_bob), ("head", head_bob),
         ("arm", person_bob), ("book", book_bob))


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
    hatch(d, [[(0, 760), (1920, 740), (1920, 1080), (0, 1080)]], angle=15, spacing=18,
          value=(140, 140, 144), alpha=80, seed=5, dash=(10, 30, 15), width=1.4)
    hatch(d, [[(0, 800), (1920, 780), (1920, 1080), (0, 1080)]], angle=-10, spacing=22,
          value=(130, 130, 134), alpha=70, seed=6, dash=(12, 35, 20), width=1.3)

    # 흩뿌려진 잔디들
    rnd = random.Random(21)
    for i in range(150):
        x = rnd.uniform(10, 1910)
        y = rnd.uniform(780, 1060)
        ln = rnd.uniform(10, 30)
        angle = rnd.uniform(-1.8, -1.2)
        stroke(d, [(x, y), (x + ln * math.cos(angle), y + ln * math.sin(angle))],
               value=(100, 100, 104), alpha=rnd.randint(80, 140), width=1.5, wob=0.8,
               seed=200 + i, passes=1, step=6)

    # 멀리 있는 나무
    tree = blob(1600, 680, 120, 180, bumps=6, seed=76, amp=0.15)
    stroke(d, tree + [tree[0]], value=(84, 84, 88), alpha=170, width=2.0, wob=1.2, seed=77, passes=2, step=5)
    hatch(d, [tree], angle=25, spacing=10, value=(110, 110, 114), alpha=80, seed=78,
          dash=(10, 24, 10), width=1.2)
    stroke(d, [(1590, 810), (1600, 880)], value=(70, 70, 74), alpha=200, width=4.0, wob=1.0, seed=80)

    # ---- 사람 (다리 → 몸통 → 머리 → 팔)
    legs = new("legs", seed=31, reveal=(1.8, 2.7), direction=(1.0, 0.2), blur=0.5, gain=1.16)
    d = legs.d

    # 먼 쪽 다리 (살짝 보임)
    FAR_LEG = [(1050, 840), (950, 780), (880, 700), (840, 840)]
    stroke(d, catmull(FAR_LEG, 8), value=(124, 124, 128), alpha=145, width=2.2, wob=1.6, seed=32, passes=1)

    # 가까운 다리 (무릎 굽힘)
    OUT_LEG = [HIP_PT, (980, 850), (900, 810), KNEE_PT, (790, 720), FOOT_PT]
    IN_LEG = [(1100, 810), (970, 750), (870, 650), KNEE_PT, (830, 740), (790, 850)]
    trouser = catmull(OUT_LEG, 8) + list(reversed(catmull(IN_LEG, 8)))

    hatch(d, [trouser], angle=70, spacing=8, value=(118, 118, 122), alpha=95, seed=39,
          dash=(16, 34, 8), width=1.5)
    stroke(d, catmull(OUT_LEG, 8), value=(42, 42, 46), alpha=222, width=3.2, wob=1.6, seed=34)
    stroke(d, catmull(IN_LEG, 8), value=(76, 76, 80), alpha=170, width=2.0, wob=1.3, seed=35, passes=1)

    # 신발
    SHOE = [(740, 870), (720, 890), (660, 895), (650, 880), (700, 860)]
    stroke(d, SHOE + [SHOE[0]], value=(46, 46, 50), alpha=222, width=3.0, wob=1.3, seed=41)
    fill_ink(d, [SHOE + [SHOE[0]]], angle=-24, value=(88, 88, 92), alpha=95, seed=87,
             spacing=3.6, width=2.2)

    torso = new("torso", seed=41, reveal=(2.5, 3.4), direction=(0.15, 1.0), blur=0.5, gain=1.16)
    d = torso.d
    stroke(d, catmull(BACK, 12), value=(40, 40, 44), alpha=218, width=3.0, wob=1.9, seed=42)
    stroke(d, catmull(CHEST, 10), value=(58, 58, 62), alpha=190, width=2.3, wob=1.7, seed=43)
    hatch(d, [BACK + list(reversed(CHEST))], angle=-35, spacing=8, value=(120, 120, 124),
          alpha=100, seed=46, dash=(16, 34, 8), width=1.5)
    hatch(d, [BACK + list(reversed(CHEST))], angle=45, spacing=13, value=(132, 132, 136),
          alpha=70, seed=47, dash=(14, 30, 10), width=1.3)

    # 옷 주름
    stroke(d, catmull([(1090, 480), (1050, 550), (1030, 680)], 6), value=(112, 112, 116),
           alpha=110, width=1.6, wob=1.1, seed=91, passes=1)

    head = new("head", seed=51, reveal=(3.2, 3.9), direction=(0.25, 1.0), blur=0.45, gain=1.16)
    d = head.d
    HP = lambda pts: rot_pts(_dy(pts), HEAD_C, HEAD_TILT)
    stroke(d, catmull(FACE, 9), value=(40, 40, 44), alpha=225, width=3.0, wob=1.2, seed=54)
    fill_ink(d, [HAIR], angle=72, value=(58, 58, 62), alpha=120, seed=61, spacing=3.0, width=2.4)
    fill_ink(d, [HAIR], angle=12, value=(72, 72, 76), alpha=55, seed=62, spacing=4.4, width=2.0)
    stroke(d, HAIR + [HAIR[0]], value=(40, 40, 44), alpha=225, width=3.0, wob=1.3, seed=52)
    # 눈 (아래를 향해 감은 형태)
    stroke(d, HP([(950, 380), (965, 385), (975, 380)]), value=(48, 48, 52), alpha=215,
           width=2.3, wob=0.7, seed=58)
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

    hatch(d, [sleeve], angle=-45, spacing=8, value=(126, 126, 130), alpha=78, seed=74,
          dash=(14, 32, 8), width=1.4)
    hatch(d, [fore], angle=-20, spacing=8, value=(128, 128, 132), alpha=68, seed=78,
          dash=(12, 30, 8), width=1.3)

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
    fill_ink(d, [L_PAGE, R_PAGE], angle=10, value=(220, 220, 224), alpha=200, seed=82,
             spacing=2.0, width=2.0)

    # 책 외곽선
    stroke(d, L_PAGE, value=(30, 30, 35), alpha=230, width=2.5, wob=0.8, seed=83)
    stroke(d, R_PAGE, value=(30, 30, 35), alpha=230, width=2.5, wob=0.8, seed=84)
    stroke(d, SPINE, value=(50, 50, 55), alpha=200, width=2.0, wob=0.5, seed=85)

    # 책 안의 글자(텍스처 느낌의 해칭)
    hatch(d, [L_PAGE], angle=30, spacing=5, value=(100, 100, 105), alpha=120, seed=86,
          dash=(3, 10, 4), width=1.0)
    hatch(d, [R_PAGE], angle=-10, spacing=5, value=(100, 100, 105), alpha=120, seed=87,
          dash=(3, 10, 4), width=1.0)

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
