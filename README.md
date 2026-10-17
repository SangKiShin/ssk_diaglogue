# 목탄 만화풍 모션그래픽 — 벤치에 앉아 생각하는 사람

모노톤 목탄(숯) 질감 위에 만화 문법으로 그린 절차적 렌더. 굵은 윤곽선·의상 볼륨(바지·소매
닫힌 형태)·진한 머리 뭉치·단색 그림자에 워블/끊김 스트로크와 해칭을 유지하고, 사람·벤치·
해칭·그레인·문구를 전부 코드로 그려 ffmpeg로 mp4 인코딩한다(이미지 생성 모델 미사용).

## 구성 관계

두 스크립트는 **실행 순서 의존이 아니라 소스 import 의존**이다.

```
make_motion.py  ← 그림 엔진 (씬 레이어·모션·질감 함수)
   │
   ├─ 단독 실행(render)  → out/charcoal_bench.mp4   (13.8초 고정 문구 컷)
   │
   └─ import ← make_dialogue.py                     (타이밍·텍스트만 추가)
        └─ 단독 실행         → out/dialogue_bench.mp4
```

- `make_dialogue.py`는 실행마다 `make_motion.build_scene()`을 새로 호출해 모든 프레임을
  자체 렌더한다. make_motion이 미리 만든 mp4는 입력이 아니므로 **make_motion 실행 없이
  바로** `make_dialogue.py`를 돌릴 수 있다. 필요한 건 두 파일이 같은 디렉터리에 있을 것뿐.
- 역할 분리 — **그림**(무엇을 어떻게 그릴까)은 `make_motion.py`, **연출**(언제 어떤 문구를
  말풍선으로 띄울까)은 `make_dialogue.py`가 담당한다. 그림을 바꾸고 싶으면 make_motion.py만,
  대사·타이밍만 바꾸고 싶으면 make_dialogue.py(또는 txt)만 고치면 된다.

### `make_motion.py` 수정이 대사 영상에 반영되는 범위

make_motion.py를 고치고 다시 실행하면 그림이 그대로 바뀐다.

| 수정 대상 | 반영 |
|---|---|
| 그림(지오메트리·선·채움·색·해칭·배경 소품) | 자동 |
| 말풍선 위치·크기(`BUBBLE_C`, `BUBBLE_RX/RY`, `TRAILS`) | 자동 — 텍스트 폭/줄바꿈 한계도 파생 |
| 리빌 타이밍(`reveal=(시작, 끝)`) | 자동 — 첫 말풍선 시각이 마지막 리빌 종료 + 0.5s로 유도됨 |
| 종이 질감·비네팅·그레인·먼지 | 자동 |
| 레이어 이름(`bg/bench/legs/torso/head/arm/trail0-2/cloud`) | **계약** — 이름을 바꾸면 make_dialogue 합성 순서도 고쳐야 함 |
| 호흡 시작 시각(5.6s, `person_bob` 등 내부) | 하드코딩 — 리빌을 크게 늘렸다면 함께 수정 |
| `out/charcoal_bench.mp4` (make_motion 실행 결과) | **무관** — 대사 영상의 입력이 아니다 |

## 산출물

| 파일 | 내용 |
|---|---|
| `out/charcoal_bench.mp4` | 1920×1080 · 30fps · 13.8초 · h264(crf21) · 무음 |
| `out/poster.png` | 1920×1080 대표 정지컷(t=12.2s) |
| `preview/` | 제작 중 확인용 스틸(t=5.2 / 7.2 / 9.5s)과 최종 프레임 |

`out/`·`preview/`는 `.gitignore` 대상(재생성 가능 산출물)이다 — 위 명령으로 다시 만든다.

## 재생성

```bash
cd ~/WS/assets/charcoal-bench
python3 make_motion.py stills 5.2 7.2 9.5 12.2   # 특정 시각 PNG 미리보기
python3 make_motion.py render                    # out/charcoal_bench.mp4 (약 1.5분)
```

## 대사 시퀀스 (`make_dialogue.py`)

txt의 비어있지 않은 줄 1줄 = 생각풍선 1개. 꼬리 팝 → 구름 팝 → 타이핑 → hold →
페이드아웃을 줄 수만큼 반복한다. 화면·질감·인물 모션은 `make_motion.py`를 재사용.

```bash
python3 make_dialogue.py sample_dialogue.txt                  # out/dialogue_bench.mp4 + dialogue_poster.png
python3 make_dialogue.py sample_dialogue.txt stills 8 12 20   # preview/dt*.png 미리보기
python3 make_dialogue.py my.txt -o out/x.mp4 --cps 12 --hold 1.2
```

| 옵션 | 기본 | 뜻 |
|---|---|---|
| `--cps` | 10 | 타이핑 속도(자/초) |
| `--hold` | 1.4 | 타이핑 끝 후 유지(초) |
| `-o` | `out/dialogue_bench.mp4` | 출력 경로 |
| `--poster-t` | 마지막 줄 hold 중간 | 포스터 시각(초) |

긴 줄은 풍선 안에서 자동 줄바꿈하고, 3줄을 넘으면 폰트를 52→22까지 줄여 맞춘다.

## 구성

- **화면**: 지평선 + 바닥 해칭 + 낙엽 + 잔디 + 먼 나무·덤불 + 멀리 나는 새 / 벤치 /
  인물(다리·몸통·머리·팔 레이어, 만화식 볼륨·프로파일 얼굴·감은 눈)
- **질감**: 종이 섬유(mottle) 베이스 → 목탄 스트로크(다중 패스 + 워블 + 끊김) → 해칭·
  단색 채움(`fill_ink`) → 비네팅 → 프레임 그레인(반해상도, 2프레임 주기)
- **모션**: 0.7s 배경 → 1.9s 벤치 → 3.0s 다리 → 3.5s 몸통 → 4.2s 머리 → 4.8s 팔 순으로
  거리장 기반 스윕으로 "그려지는" 리빌, 5.6s부터 호흡(몸통 상하 1.1px + 머리 지연 진동),
  6.05s부터 생각풍선 꼬리 3개 팝(오버슈트), 6.75s 구름 팝, 7.9~10.4s 문구 타이핑,
  12.9s부터 종이색으로 페이드 아웃

## 주요 파라미터 (`make_motion.py`)

| 상수 | 뜻 |
|---|---|
| `LINE1` / `LINE2` | 풍선 안 두 줄 문구 |
| `TYPING_T0` / `TYPING_T1` | 타이핑 시작·종료 시각 |
| `DUR`, `FPS` | 총 길이, 프레임레이트 |
| `P_DY` | 인물(상체·골반·머리·팔) 상하 오프셋 |
| `HEAD_TILT` | 고개 숙임 각도(도) |
| `cloud_motion` / `trail_motion` | 풍선 팝·부유 모션 |
| `person_bob` / `head_bob` | 호흡 모션 함수 |

폰트는 NanumSquareB(`/usr/share/fonts/truetype/nanum/NanumSquareB.ttf`)를 쓴다.
레이어별 `gain`은 잉크 진하기, `blur`는 목탄 번짐 정도다.
