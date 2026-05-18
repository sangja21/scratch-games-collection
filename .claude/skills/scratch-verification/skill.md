---
name: scratch-verification
description: 빌드된 .sb3 파일의 구조 무결성과 plan 과의 일치성을 검증하는 절차. scratch-verifier 에이전트가 호출. zip 검사, project.json 파싱, 변수·메시지·블록 카운트 대조, 자산 해시 일치 등 모든 검증 단계를 담는다.
---

# scratch-verification

## 검증의 두 축

1. **구조 무결성** — zip/JSON 자체가 손상 없이 열림
2. **plan 과의 정합성** — 빌더가 plan 의 모든 요구사항을 실제로 구현했는가

"파일이 만들어졌다" 는 검증이 아니다. plan 의 변수 목록과 project.json 의 변수 키를 **양방향** 으로 대조하는 게 핵심.

## 구조 검증 스크립트

```python
import json, zipfile, hashlib, sys

def verify_structure(sb3_path: str) -> list[str]:
    issues = []
    with zipfile.ZipFile(sb3_path) as zf:
        bad = zf.testzip()
        if bad: issues.append(f"corrupted entry: {bad}")
        names = zf.namelist()
        if "project.json" not in names:
            issues.append("missing project.json")
            return issues
        with zf.open("project.json") as f:
            try:
                project = json.load(f)
            except json.JSONDecodeError as e:
                issues.append(f"project.json parse error: {e}")
                return issues
        # 자산 해시 일치 확인
        for target in project["targets"]:
            for asset in target.get("costumes", []) + target.get("sounds", []):
                aid = asset["assetId"]
                md5ext = asset["md5ext"]
                if md5ext not in names:
                    issues.append(f"missing asset file: {md5ext}")
                    continue
                with zf.open(md5ext) as af:
                    actual_md5 = hashlib.md5(af.read()).hexdigest()
                if actual_md5 != aid:
                    issues.append(f"asset MD5 mismatch: {md5ext} (declared {aid}, actual {actual_md5})")
        # 메타데이터
        if project.get("meta", {}).get("semver") != "3.0.0":
            issues.append(f"unexpected semver: {project.get('meta',{}).get('semver')}")
        if not project["targets"][0].get("isStage"):
            issues.append("first target is not Stage")
    return issues
```

## 블록 그래프 검증

```python
def verify_block_graph(target: dict) -> list[str]:
    """한 sprite/stage 안의 blocks dict 가 일관된지 확인."""
    issues = []
    blocks = target["blocks"]
    ids = set(blocks.keys())
    for bid, b in blocks.items():
        nxt = b.get("next")
        par = b.get("parent")
        if nxt and nxt not in ids:
            issues.append(f"[{target['name']}] block {bid} next→{nxt} not found")
        if par and par not in ids:
            issues.append(f"[{target['name']}] block {bid} parent→{par} not found")
        # input slot 안의 block 참조도 검증
        for key, inp in b.get("inputs", {}).items():
            # inp 는 [type, val] 또는 [type, val, shadow]
            for slot_val in inp[1:]:
                if isinstance(slot_val, str) and slot_val and slot_val not in ids:
                    issues.append(f"[{target['name']}] block {bid} input {key} → {slot_val} not found")
                elif isinstance(slot_val, list):
                    # 리터럴 슬롯 - 무시
                    pass
    return issues
```

## plan 대조 검증

```python
import re

def parse_plan_entities(plan_md: str) -> dict:
    """plan-{slug}.md 에서 변수/메시지/스프라이트 이름 추출."""
    vars_ = re.findall(r"V_[A-Z_]+", plan_md)
    brs = re.findall(r"BR_[A-Z_]+", plan_md)
    lists = re.findall(r"L_[A-Z_]+", plan_md)
    return {"vars": set(vars_), "broadcasts": set(brs), "lists": set(lists)}

def parse_project_entities(project: dict) -> dict:
    """project.json 에서 사용 가능한 ID 집합 추출."""
    stage = project["targets"][0]
    return {
        "vars": set(stage["variables"].keys()),
        "broadcasts": set(stage["broadcasts"].keys()),
        "lists": set(stage["lists"].keys()),
    }

def diff_entities(plan: dict, proj: dict) -> list[str]:
    issues = []
    for kind in ("vars", "broadcasts", "lists"):
        only_plan = plan[kind] - proj[kind]
        only_proj = proj[kind] - plan[kind]
        # plan 의 V_FOO 가 project.json 에는 varFoo001 같은 hash-suffixed 가 아니라
        # 그대로 들어있어야 함. plan 의 컨벤션과 build 의 컨벤션이 일치한다고 가정.
        if only_plan:
            issues.append(f"{kind} in plan but not in project: {sorted(only_plan)}")
        if only_proj:
            issues.append(f"{kind} in project but not in plan: {sorted(only_proj)}")
    return issues
```

## 블록 카운트 sanity

| 난이도 | 블록 수 범위 |
|-------|-------------|
| ★ | 30 ~ 80 |
| ★★ | 80 ~ 150 |
| ★★★ | 150 ~ 300 |
| ★★★★ | 300 ~ 500 |
| ★★★★★ | 500+ |

`sum(len(t["blocks"]) for t in project["targets"])` 로 계산. 범위 밖이면 경고.

## 전체 검증 흐름 (verifier 의 작업 순서)

1. **구조** — `verify_structure(sb3_path)` 호출. 이슈가 있으면 builder 에게 즉시 보고하고 중단.
2. **블록 그래프** — 모든 target 에 대해 `verify_block_graph(target)`. orphan/dangling reference 확인.
3. **plan 대조** — `parse_plan_entities` ↔ `parse_project_entities` 비교.
4. **블록 카운트** — plan 의 난이도 vs 실제 블록 수.
5. **README 작성** — 모두 통과하면 `games/{slug}/README.md` 작성.

## 이슈 보고 포맷 (builder 에게 SendMessage)

```
[{slug}] 검증 실패. 이슈 N개:

1. [구조] missing asset file: abc123.svg
   → build.py 의 main() 에서 ASSETS/abc.wav 를 .build/ 에 복사하는 부분 누락. ~line XX 확인.

2. [메커닉] vars in plan but not in project: ['V_COMBO']
   → plan 에는 V_COMBO 가 정의돼 있으나 build.py 의 stage variables 에 없음. 추가 필요.

3. [블록 그래프] [Note] block b0042 parent→b0091 not found
   → b0091 이 어디서 생성되는지 확인. chain() 빠뜨림 의심.

수정 후 재빌드 부탁드립니다.
```

이슈 1개당:
- 카테고리 ([구조] / [메커닉] / [블록 그래프] / [카운트])
- 정확한 증상
- 빌더가 어디를 봐야 하는지 힌트

## 빠른 검증 one-liner

수동으로 한 게임을 빠르게 점검할 때:

```bash
python3 -c "
import json, zipfile, sys
p = sys.argv[1]
with zipfile.ZipFile(p) as zf:
    print('zip ok:', zf.testzip() is None)
    proj = json.loads(zf.read('project.json'))
    for t in proj['targets']:
        n_blocks = len(t['blocks'])
        n_vars = len(t.get('variables', {}))
        print(f\"  {t['name']}: {n_blocks} blocks, {n_vars} vars\")
" games/{slug}/{name}.sb3
```
