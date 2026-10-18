# 목탄 만화풍 모션그래픽 — 씬 선택형 생성기

모노톤 목탄(숯) 질감 위에 만화 문법으로 그린 절차적 렌더. 굵은 윤곽선·의상 볼륨·진한
머리 뭉치·단색 그림자에 워블/끊김 스트로크와 해칭을 유지하고, 사람·소품·배경·문구를
전부 코드로 그려 ffmpeg로 mp4 인코딩한다(이미지 생성 모델 미사용).

그림 엔진은 공용으로 한 벌만 있고, **장면(씬)은 `scene_*.py` 모듈로 추가**한다.
사용자는 `--scene`으로 씬을 골라 단독 컷이든 대사 시퀀스든 같은 방식으로 만든다.

## 구성 관계

```
engine.py  ← 그림 엔진 (스트로크·해칭·레이어·질감·후처리·인코딩 + 씬 발견)
   │
   ├─ scene_bench.py    벤치 씬   (지오메트리·레이어·모션·씬 메타)
   ├─ scene_reading.py  풀밭 독서 씬
   ├─ scene_guitar.py   클래식 기타 연주 씬
   │
   ├─ make_motion.py    단독 컷 CLI   → out/charcoal_<씬>.mp4 + <씬> 포스터
   └─ make_dialogue.py  대사 시퀀스 CLI → out/dialogue_<씬>.mp4
```

- 씬 모듈은 "무엇을 그릴까"(지오메트리·레이어·모션·문구·출력 파일명)만 정의하고,
  "어떻게 그릴까"(스트로크·해칭·질감·합성·인코딩)는 engine.py가 담당한다.
- `make_dialogue.py`는 실행마다 `씬.build_scene()`을 새로 호출해 모든 프레임을 자체
  렌더한다. make_motion이 미리 만든 mp4는 입력이 아니므로 **make_motion 실행 없이
  바로** `make_dialogue.py`를 돌릴 수 있다.
- 씬 합성 순서는 씬의 `ORDER` 튜플 한 곳에 정의되어 make_motion(단독 컷)과
  make_dialogue(대사 시퀀스)가 같은 순서를 공유한다.

## 씬 목록

| `--scene` | 설명 | 단독 컷 출력 |
|---|---|---|
| `bench` (기본) | 벤치에 앉아 생각하는 사람 | `out/charcoal_bench.mp4` |
| `reading` | 풀밭에 무릎 세우고 책 읽는 사람 | `out/charcoal_reading.mp4` |
| `guitar` | 클래식 기타를 연주하는 사람 | `out/charcoal_guitar.mp4` |

## 사용법

```bash
cd ~/WS/assets/charcoal-bench
python3 make_motion.py --list                            # 씬 목록
python3 make_motion.py stills 5.2 7.2 9.5 12.2           # 기본 씬(bench) 미리보기 PNG
python3 make_motion.py render                            # out/charcoal_bench.mp4 (약 5~8분)
python3 make_motion.py --scene reading render            # out/charcoal_reading.mp4
python3 make_motion.py --scene reading stills 2.0 9.3    # 지정 씬 미리보기
```

## 대사 시퀀스 (`make_dialogue.py`)

txt의 비어있지 않은 줄 1줄 = 생각풍선 1개. 꼬리 팝 → 구름 팝 → 타이핑 → hold →
페이드아웃을 줄 수만큼 반복한다. 화면·질감·인물 모션은 선택한 씬을 재사용한다.

```bash
python3 make_dialogue.py sample_dialogue.txt                  # bench 씬 + 대사
python3 make_dialogue.py --scene reading sample_dialogue.txt  # reading 씬 + 대사
python3 make_dialogue.py sample_dialogue.txt stills 8 12 20   # preview/dt*.png 미리보기
python3 make_dialogue.py my.txt --scene reading -o out/x.mp4 --cps 12 --hold 1.2
```

| 옵션 | 기본 | 뜻 |
|---|---|---|
| `--scene` | `bench` | 씬 id (`scene_<id>.py`) |
| `--cps` | 10 | 타이핑 속도(자/초) |
| `--hold` | 1.4 | 타이핑 끝 후 유지(초) |
| `-o` | `out/dialogue_<씬>.mp4` | 출력 경로 |
| `--poster-t` | 마지막 줄 hold 중간 | 포스터 시각(초) |

출력 mp4·포스터는 `dialogue_<씬>.mp4`·`dialogue_<씬>_poster.png`로 씬별로 구분 저장된다.
긴 줄은 풍선 안에서 자동 줄바꿈하고, 3줄을 넘으면 폰트를 64→22까지 줄여 맞춘다.
풍선 크기(`BUBBLE_RX/RY`)는 씬 값에서 파생되므로 씬마다 자동으로 맞는다.

## 씬 추가하기

`scene_<id>.py` 파일 하나를 만들면 `--list`와 `--scene <id>`에 자동으로 잡힌다.
파일명의 `<id>`가 곧 선택자다.

필수 계약(engine.py 모듈 독스트링과 동일):

| 심볼 | 뜻 |
|---|---|
| `DESC` | `--list` 표시용 설명 |
| `DUR`, `OUT_MP4`, `POSTER_PNG`, `POSTER_T` | 길이(초), 단독 컷 출력 파일명, 포스터 시각 |
| `BUBBLE_C`, `BUBBLE_RX`, `BUBBLE_RY`, `TRAILS` | 생각풍선 중심·반경·꼬리 위치 |
| `TYPING_T0`, `TYPING_T1` | 단독 컷 문구 타이핑 시작·종료 시각 |
| `TEXT_LINES`, `TEXT_SIZE`, `TEXT_DY` | 단독 컷 문구(줄 수 무관), 폰트 크기, 줄별 y 오프셋 |
| `build_scene()` | `{"이름": Layer, ...}` 레이어 사전 (마지막에 `prep()` 호출) |
| `ORDER` | 합성 순서 튜플 `(("bg", None), ("legs", legs_bob), ...)` — 이동 함수 없는 레이어는 `None` |

공용으로 제공되는 것(engine에서 import): `stroke`/`hatch`/`fill_ink`/`catmull`/`blob`/
`ellipse_poly`/`Layer`/`smoothstep` 등 드로잉 유틸과 `trail_pop(i, t0)`/`cloud_pop(t0)`
말풍선 팝 모션, 타이핑 상수(`TRAIL_T0` `TRAIL_GAP` `T_CLOUD` `T_TYPE_DELAY` `T_FADE`).

레이어 이름 규칙: 생각풍선은 `trail0..N-1`(개수 = `len(TRAILS)`)과 `cloud` 고정이고,
그 외 이름은 씬 자유 — `ORDER`에 쓴 이름만 `build_scene()` 결과에 있으면 된다.

### 씬 수정이 두 CLI에 반영되는 범위

| 수정 대상 | 단독 컷 | 대사 시퀀스 |
|---|---|---|
| 지오메트리·선·채움·색·해칭·배경 소품 | 자동 | 자동 |
| 말풍선 위치·크기(`BUBBLE_*`, `TRAILS`) | 자동 | 자동 — 텍스트 폭/줄바꿈 한계도 파생 |
| 리빌 타이밍(`reveal=(시작, 끝)`) | 자동 | 자동 — 첫 말풍선 시각이 마지막 리빌 종료 + 0.5s로 유도됨 |
| `ORDER`(합성 순서·이동 함수) | 자동 | 자동 |
| 종이 질감·비네팅·그레인·먼지(engine) | 자동 | 자동 |
| 호흡 시작 시각(5.6s, `person_bob` 등 씬 내부) | 하드코딩 | 동일 — 리빌을 크게 늘렸다면 함께 수정 |

## 산출물

| 파일 | 내용 |
|---|---|
| `out/charcoal_bench.mp4` | bench 단독 컷 · 1920×1080 · 30fps · 13.8초 · h264(crf21) · 무음 |
| `out/charcoal_reading.mp4` | reading 단독 컷 · 동일 사양 |
| `out/charcoal_guitar.mp4` | guitar 단독 컷 · 동일 사양 |
| `out/poster.png` / `out/reading_poster.png` | 씬별 대표 정지컷(t=12.2s) |
| `out/dialogue_<씬>.mp4` + `out/dialogue_<씬>_poster.png` | 대사 시퀀스 결과 |
| `preview/` | 제작 중 확인용 스틸(`t*.png` 단독, `dt*.png` 대사) |

`out/`·`preview/`는 `.gitignore` 대상(재생성 가능 산출물)이다 — 위 명령으로 다시 만든다.

## 구성

- **공용(engine.py)**: 종이 섬유(mottle) 베이스 → 목탄 스트로크(다중 패스 + 워블 + 끊김) →
  해칭·단색 채움(`fill_ink`) → 비네팅 → 프레임 그레인(반해상도, 2프레임 주기) → 먼지 →
  페이드 인/아웃. 말풍선 팝(오버슈트 + 부유)과 타이핑 커서도 공용.
- **bench 씬**: 지평선 + 바닥 해칭 + 낙엽 + 잔디 + 먼 나무·덤불 + 멀리 나는 새 / 벤치 /
  인물(다리·몸통·머리·팔, 만화식 볼륨·프로파일 얼굴·감은 눈). 리빌은 0.7s 배경 →
  1.9s 벤치 → 3.0s 다리 → 3.5s 몸통 → 4.2s 머리 → 4.8s 팔 순.
- **reading 씬**: 언덕 풀밭 + 멀리 나무 / 무릎 세운 다리·숙인 상체·감은 눈·펼친 책 레이어.
  리빌은 0.7s 배경 → 1.8s 다리 → 2.5s 몸통 → 3.2s 머리 → 3.8s 팔 → 4.0s 책 순.
- **guitar 씬**: 바닥 + 뮤직 스탠드 / 스툴에 앉은 다리·상체·머리 / 몸통·넥·사운드홀·6현을
  로컬 좌표(넥이 -y)로 그린 뒤 `G_ANG`(-40°) 회전해 눕힌 클래식 기타 / 넥을 짚는 왼팔·
  스트럼하는 오른팔. 리빌은 0.7s 배경 → 1.4s 스탠드 → 1.8s 스툴 → 2.6s 다리 → 3.3s 몸통
  → 4.0s 머리 → 4.4s 기타 → 4.9s 왼팔 → 5.0s 오른팔 순. 생각풍선은 우상단(넥과 안 겹침).

폰트는 NanumSquareB(`/usr/share/fonts/truetype/nanum/NanumSquareB.ttf`).
레이어별 `gain`은 잉크 진하기, `blur`는 목탄 번짐 정도다.

## 히스토리 메모

2026-10 이전은 단일 스크립트(`make_motion.py` 벤치 씬)였고, `make_motion2.py`(풀밭
독서)가 변형으로 추가되었다가 위 구조로 개편되었다. 개편 커밋은 구 단일 스크립트와
프레임 바이트 일치(parity)를 검증 후 진행했다: bench/reading 단독 컷 + 대사 bench
시퀀스에서 시점별 픽셀 완전 동일. 구 스크립트 원문은 개편 커밋 이전 히스토리
(0f3efc9)에 있다.