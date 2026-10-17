#!/usr/bin/env python3
"""목탄 만화풍 모션그래픽 생성기 — 씬 선택 CLI.

씬은 scene_*.py 모듈로 추가한다(계약: engine.py 모듈 독스트링·README "씬 추가하기").

  python3 make_motion.py --list                       # 씬 목록
  python3 make_motion.py stills 1.0 3.0 6.0           # 기본 씬(bench) 미리보기 PNG
  python3 make_motion.py render                       # 기본 씬(bench) mp4
  python3 make_motion.py --scene reading render       # 씬 지정
"""
import argparse
import os

from PIL import Image

import engine as eng


def main():
    ap = argparse.ArgumentParser(description="씬 선택 목탄 모션그래픽 생성기")
    ap.add_argument("--scene", default="bench", help="씬 id (scene_<id>.py, 기본: bench)")
    ap.add_argument("--list", action="store_true", help="씬 목록을 표시하고 종료")
    ap.add_argument("-o", "--out", default=None, help="출력 mp4 경로(기본 out/<씬>.mp4)")
    ap.add_argument("mode", nargs="?", default="stills", choices=["render", "stills"],
                    help="stills=미리보기 PNG(기본), render=mp4")
    ap.add_argument("times", nargs="*", type=float, help="stills 모드 시각(초)")
    args = ap.parse_args()

    if args.list:
        for sid, mod in eng.find_scenes().items():
            print("%-10s %s → out/%s" % (sid, mod.DESC, mod.OUT_MP4))
        return

    scene = eng.load_scene(args.scene)
    os.makedirs(eng.OUT, exist_ok=True)
    os.makedirs(eng.PREV, exist_ok=True)
    sc = eng.Scene(scene)

    if args.mode == "stills":
        times = args.times or [2.5, 5.0, 7.2, 9.0, 13.0]
        for t in times:
            img = Image.fromarray(sc.render(t))
            p = os.path.join(eng.PREV, "t%05.2f.png" % t)
            img.save(p)
            print("wrote", p)
        return

    dst = args.out or os.path.join(eng.OUT, scene.OUT_MP4)
    eng.render_mp4(sc.render, scene.DUR, dst)
    poster = Image.fromarray(sc.render(scene.POSTER_T))
    poster.save(os.path.join(eng.OUT, scene.POSTER_PNG))
    print("done", dst)


if __name__ == "__main__":
    main()
