---
name: build-curriculum-batch
description: Scratch 게임 후보 N개를 자동으로 빌드하는 오케스트레이터. docs/game-candidates.md 의 "단원별 심화 후보" 섹션에서 단원(지수/로그 · 벡터 · 사인)이나 개별 게임을 지정하면, planner/builder/verifier 팀을 띄워 plan → build → verify 사이클을 완주한다. "단원 다 만들자", "벡터 게임 모두 빌드", "○○ 게임 만들어줘" 같은 요청에 반드시 이 스킬을 사용할 것.
---

# build-curriculum-batch

`docs/game-candidates.md` 의 후보를 자동 빌드하는 팀 오케스트레이터. scratch-supervisor 가 리더로서 scratch-planner / scratch-builder / scratch-verifier 와 협업.

## 트리거 상황

- "지수/로그 단원의 후보들 다 빌드해줘"
- "벡터 게임 3개 만들어"
- "삼각함수 서핑 만들어줘"
- "단원별 심화 후보 전체 빌드"
- "박테리아 디펜스 패턴으로 반감기 광산도 만들어줘"

## 실행 모드: 에이전트 팀

scratch-supervisor 가 팀 리더로서 TaskCreate 로 작업 큐를 관리. planner/builder/verifier 가 자체 조율하며 처리. 모든 Agent 호출에 `model: "opus"` 명시.

## 입력 파라미터

| 파라미터 | 설명 | 기본값 |
|---------|------|-------|
| `domain` | "지수/로그" \| "벡터" \| "사인" \| "전체" \| 개별 게임 리스트 | "전체" |
| `max_concurrent` | 동시에 진행할 게임 수 | 2 |
| `skip_existing` | `games/{slug}/` 가 이미 있으면 건너뛰기 | true |
| `dry_run` | 작업 큐만 생성 후 중단 | false |

## Phase 1 — 작업 분해 (supervisor)

1. `docs/game-candidates.md` 의 "📐 단원별 심화 후보" 섹션 파싱
2. `domain` 입력에 해당하는 후보 추출. 각 후보에 대해 다음 메타 추출:
   - `slug` (kebab-case, 예: `radioactive-mine`)
   - `name` (한국어, 예: `반감기 광산`)
   - `category`, `mechanics`, `learning_point`, `difficulty`
3. `skip_existing` 적용 — 이미 존재하는 게임 제외
4. 각 후보당 3개 작업 생성:
   - `plan-{slug}` — planner 가 처리
   - `build-{slug}` — builder 가 처리 (blockedBy: plan-{slug})
   - `verify-{slug}` — verifier 가 처리 (blockedBy: build-{slug})
5. `dry_run: true` 면 작업 큐만 보여주고 중단

## Phase 2 — 팀 가동 (supervisor + specialists)

supervisor 가 specialist 들에게 작업 할당. 각 specialist 는 자기 작업을 picking 해서 처리.

```
supervisor → TaskCreate (plan-A, build-A, verify-A, plan-B, build-B, ...)
planner    → 작업 큐에서 plan-* 작업을 순서대로 처리, docs/plan-*.md 작성
builder    → plan 완료된 게임의 build-* 작업 처리, games/*/build.py 작성 + 실행
verifier   → build 완료된 게임의 verify-* 작업 처리, README 작성
```

병렬화: planner 가 게임 B plan 을 쓰는 동안 builder 가 게임 A build 를 만들 수 있음. supervisor 가 `max_concurrent` 를 초과하지 않도록 조절.

### 수정 루프

- verifier 가 이슈 발견 → builder 에게 SendMessage (작업은 in_progress 유지)
- builder 가 재빌드 → verifier 가 재검증
- 3회 왕복하면 supervisor 가 개입해서 작업을 "blocked" 처리

## Phase 3 — 산출물 갱신 (supervisor)

모든 verify 작업 완료 후:

1. `README.md` 의 게임 표에 새 게임 행 추가 (기존 [박테리아 디펜스](...) 행과 같은 포맷)
2. `docs/game-candidates.md` 의 "현재 컬렉션 상태" 줄과 "단원별 심화 후보" 의 해당 행에 `✅ (완료)` 마킹
3. 최종 보고서를 사용자에게 반환

## 데이터 전달 프로토콜

| 산출물 | 위치 | 생성자 | 사용자 |
|--------|------|--------|--------|
| 작업 큐 | TaskCreate (내부) | supervisor | 전원 |
| plan 문서 | `docs/plan-{slug}.md` | planner | builder, verifier |
| build.py | `games/{slug}/build.py` | builder | verifier |
| .sb3 | `games/{slug}/{name}.sb3` | builder | verifier (검증), 사용자 (최종) |
| README | `games/{slug}/README.md` | verifier | 사용자 |
| 검증 이슈 | SendMessage | verifier | builder (수정용) |

## 에러 핸들링

| 상황 | 처리 |
|------|------|
| planner 가 후보 정보 부족으로 멈춤 | supervisor 에게 SendMessage. supervisor 가 사용자에게 추가 정보 요청 또는 후보를 큐에서 제외 |
| builder 가 python 실행 실패, 2회 재시도 실패 | 작업을 "blocked" 마킹. 해당 게임은 건너뛰고 나머지 진행. 최종 보고서에 누락 명시 |
| verifier 가 3회 왕복 후에도 미해결 | 작업을 "blocked" 마킹. plan 자체에 모순이 있을 가능성 — 사용자 확인 요청 |
| 동시에 같은 자원 수정 충돌 | TaskCreate 의존성으로 plan→build→verify 순서를 강제하므로 발생하지 않아야 함 |

## 테스트 시나리오

### 정상 흐름

```
사용자: "사인함수 단원에서 파형 매칭만 만들어줘"
→ supervisor:
   - candidates 파싱 → wave-matching 추출
   - TaskCreate(plan-wave-matching, build-wave-matching, verify-wave-matching)
→ planner: docs/plan-wave-matching.md 작성
→ builder: games/wave-matching/build.py 작성 + python3 실행 → 파형_매칭.sb3 생성
→ verifier:
   - 구조 검증 통과
   - plan 의 V_AMP, V_FREQ, V_PHASE 가 project.json 에 모두 있음
   - 블록 카운트 ~180 (★★★ 범위)
   - games/wave-matching/README.md 작성
→ supervisor: README.md + game-candidates.md 갱신, 보고
```

### 에러 흐름

```
사용자: "지수/로그 단원 전부 빌드"
→ supervisor: 6개 후보 큐잉
→ planner: 6개 plan 순서대로 작성
→ builder: 반감기 광산 build.py 작성, 실행 → KeyError: 'V_HALFLIFE'
   → 2회 재시도 후에도 실패 → 작업 blocked
→ supervisor: 반감기 광산은 누락 마킹, 나머지 5개 계속 진행
→ 최종 보고: 5/6 성공, "반감기 광산은 빌드 실패 — V_HALFLIFE 변수 정의 누락. plan 의 변수 섹션 확인 필요"
```

## 참고 스킬

- 빌더는 `scratch-game-template` + `scratch-sb3-format` 참조
- 검증자는 `scratch-verification` 참조
- 모든 에이전트 정의: `.claude/agents/scratch-{supervisor,planner,builder,verifier}.md`
