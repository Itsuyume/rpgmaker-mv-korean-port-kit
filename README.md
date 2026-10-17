# RPG Maker MV 한국어·macOS 이식 도구

MV의 표시 문자열을 문맥별로 추출하고, 번역을 검증한 뒤 별도 게임 사본에 적용한다. macOS 부분은 고정된 NW.js arm64 런타임과 Noto Sans CJK KR 글꼴을 사용해 앱을 구성한다.

게임 원본·대사·번역·실제 카탈로그·게임 자산·세이브·NW.js 바이너리는 포함하지 않는다. 도구는 번역 모델이나 외부 서비스를 호출하지 않는다. 현재 앱 설정은 NYD412 입력 구조에 맞춰 고정돼 있으므로 다른 MV 게임에는 표시 필드와 플러그인 계약을 먼저 확인해야 한다.

## 구성

| 경로 | 역할 |
| --- | --- |
| `pq_catalog/` | 표시 위치, 문맥 입력, 토큰, 번역 검증과 적용 |
| `runtime/` | 앱 구성, 한글 글꼴, 앱 바깥 전용 저장 경로, 미디어 검사 |
| `runtime/shared/` | 출처와 해시가 고정된 기존 공용 도구 |
| `checks/` | 모듈 순환·계층 위반·파일 및 함수 크기 검사 |
| `tests/` 및 `runtime/tests/` | 합성 자료와 임시 파일을 사용하는 행동 검사 |

`pq_catalog`와 `runtime`은 파일 경로와 보고서로 연결한다. 파일 해시용 순수 공용 함수 하나 외에는 서로의 구현을 import하지 않는다. 모듈별 계약은 [카탈로그](pq_catalog/ARCHITECTURE.md), [런타임](runtime/ARCHITECTURE.md)에 있다.

## 검사

Python 3.11 이상과 Node.js가 필요하다. 앱 복사·서명과 CoreText 검사는 macOS 기본 도구를 사용한다. 미디어 검사에는 별도로 `ffprobe`를 지정한다.

```sh
python3 -m pip install -r requirements-dev.txt
python3 -B checks/architecture.py
python3 -m mypy --strict --follow-imports=silent --python-version 3.11 pq_catalog
PYTHONPATH=. python3 -B -m unittest discover -s tests/architecture -v
PYTHONPATH=. python3 -B -m unittest discover -s tests/catalog -v
python3 -B -m unittest discover -s runtime/tests -p 'test_*.py' -v
node --test runtime/tests/storage.test.js runtime/tests/font.test.js
```

엄격 타입 검사의 범위는 `pq_catalog`다. 테스트와 CI에는 실제 게임 자료나 NW.js 실행을 넣지 않는다. CI 통과만으로 게임 부팅·실제 저장 UI·영상 및 음성 재생을 확인했다고 판단하지 않는다.

## 카탈로그와 번역 적용

`PQ_SOURCE`는 읽기 전용 원본, `PQ_PROJECT`는 카탈로그와 번역을 저장할 별도 작업 폴더다. 아래 파일은 사용자가 로컬에서 준비한 실제 입력이며 저장소에 추가하지 않는다.

```sh
PYTHONPATH=. python3 -B -m pq_catalog.cli build-core \
  --www "$PQ_SOURCE/www" \
  --source-manifest "$PQ_PROJECT/quality/source-manifest.json" \
  --glossary "$PQ_PROJECT/translation/glossary.json" \
  --project "$PQ_PROJECT"

PYTHONPATH=. python3 -B -m pq_catalog.cli add-plugins \
  --www "$PQ_SOURCE/www" \
  --source-manifest "$PQ_PROJECT/quality/source-manifest.json" \
  --glossary "$PQ_PROJECT/translation/glossary.json" \
  --audit-spec "$PQ_PROJECT/quality/plugin-audit-display-spec.json" \
  --project "$PQ_PROJECT"

PYTHONPATH=. python3 -B -m pq_catalog.cli validate \
  --project "$PQ_PROJECT" --group 1 --phase core --pending 20

PYTHONPATH=. python3 -B -m pq_catalog.cli apply \
  --project "$PQ_PROJECT" --source-www "$PQ_SOURCE/www" \
  --target-www "$PQ_APP/Contents/Resources/app.nw/www" \
  --audit-spec "$PQ_PROJECT/quality/plugin-audit-display-spec.json"
```

6개 그룹의 코어 입력과 플러그인 추가 입력은 별도 manifest로 유지한다. 번역 shard는 ID와 한국어 문자열만 가진 JSON 객체다. 제어코드·숫자·줄바꿈·선택지 연결을 검사하며, 누락된 번역을 빈 문자열이나 원문으로 채우지 않는다. 적용기는 전체 번역이 유효할 때만 명시적인 대상 사본을 변경하고, 허용된 표시 위치 이외의 JSON 차이를 거부한다.

JS 추가 문구는 원본 파일 해시와 감사된 literal byte span 또는 중첩 JSON codec으로 지정한다. 내부 검색 키, 코드 표현식, `${...}` 템플릿 삽입, 명령 순서는 번역 문자열로 바꾸지 않는다.

## macOS 앱

[런타임 명령과 서명 경계](runtime/RUNTIME.md)를 따른다. 런타임과 폰트는 `runtime/runtime-lock.json`에 지정된 공식 파일 및 SHA-256과 일치해야 한다. 개인 절대 경로를 import 경로에 추가하지 않는다.

`build --prepare-only`는 서명을 확인하지 않은 준비본을 만든다. 최종 서명은 번역 적용 등 모든 변경 뒤에 수행하고, 최종 ZIP을 새로 추출해 서명·한글 표시·입력·저장/불러오기를 확인한다. 앱 내부와 연결되지 않은 전용 프로필에 저장하며 기존 세이브는 자동으로 가져오지 않는다.
