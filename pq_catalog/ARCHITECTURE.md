# RPG Maker MV 표시 문구 카탈로그

## 소유와 의존 방향

이 패키지는 원본을 읽고 표시 문구의 위치·문맥·번역 계약을 만든다. 번역 모델이나 서버를 호출하지 않는다. `source/`·기존 일본어 전용 프로젝트·다른 작업자의 runtime 모듈은 수정하지 않는다.

의존 방향은 `CLI → 카탈로그/분담/검증/적용 → 표시 선택·이벤트 문맥·토큰 → JSON 입출력·자료형`이다. 토큰·입출력 계층은 CLI·카탈로그·런타임을 역으로 import하지 않는다. 패키지 초기화 파일의 re-export는 두지 않는다. 파일 해시는 순수 leaf인 `runtime.shared.archive.sha256_file`만 직접 재사용한다. 이 명시적 예외 외에는 runtime↔catalog import를 금지하며, 런타임 부팅·전역 상태·네트워크 모듈을 읽지 않는다.

| 모듈 | 단일 책임 |
| --- | --- |
| `model.py` | JSON 경로, 발생 위치, 문맥, 문구의 명시적 자료형 |
| `json_store.py` | 중복 키 거부, 원자적 JSON 저장, 해시, 경로 읽기·쓰기 |
| `rules.py` | MV core 표시 필드와 명시적 제외 규칙의 SSOT |
| `core_fields.py` | DB·System·지도 표시 필드 |
| `event_fields.py`, `choices.py` | 이벤트 표시 문구, 문맥과 102/402 연결 |
| `tokens.py` | MV·확인된 플러그인 표식과 숫자 보존 |
| `catalog.py`, `groups.py` | 안정 ID·원본 해시·6개 문맥 입력 생성 |
| `validation.py` | shard 계약, 누락·추가·중복·빈 번역·표식 검사 |
| `application.py` | 별도 대상의 허용 표시 위치만 변경·전체 JSON 차이 검증 |
| `plugin_contract.py` | 감사된 JS/플러그인 표시 필드의 별도 입력 계약 |
| `plugin_codecs.py`, `js_strings.py`, `js_spans.py` | 중첩 JSON·JS 리터럴의 명시 codec과 보호 블록 |
| `plugin_diff.py`, `json_diff.py` | 허용한 표시 위치 외 모든 값의 재귀 비교 |
| `baseline.py`, `file_transaction.py` | 원본/대상 분리·해시 guard·사전 준비·실패 시 rollback |
| `integration.py`, `catalog_set.py` | 코어/추가분 전체 계약과 한 번의 적용 commit |

카탈로그는 `www` 기준 상대 파일명과 JSON 경로를 기록한다. 게임·인물·자산·이벤트의 내부 식별자를 번역 ID로 쓰거나 변경하지 않는다. ID는 위치/출처와 원문 해시로 정하며, 반복 문구를 합칠 때도 문맥과 모든 적용 위치를 보존한다.

## core 표시 선택

이벤트는 401·405·102/402·320·324·325만 자동 선택한다. 선택지 본문과 같은 indent의 402 분기 이름은 인덱스로 연결하며 분기 인덱스·indent·명령 순서는 바꾸지 않는다. 잘못된 연결은 숨기지 않고 위치로 보고한다.

Actors의 name/nickname/profile, Armors·Items·Weapons의 name/description, Classes·Enemies의 name, Skills의 name/description/message1/message2, States의 name/message1~4를 다룬다. System의 gameTitle/currencyUnit, 표시용 유형 배열과 terms를 다룬다. 지도는 MapNNN.json의 displayName을 대상으로 한다.

comments(108/408), scripts(355/655), labels, notes, event name, MapInfos name, switch/variable name, plugin command는 자동 번역에서 제외한다. 언어가 없는 기호·숫자 전용 문구와 명시적으로 검토한 내부 초기값은 원문 유지로 기록한다. 이름처럼 보인다는 이유만으로 내부 식별자를 일괄 치환하지 않는다.

JS와 HUD/Quest 플러그인 문구는 별도 감사 계약으로만 추가한다. 원본 파일 해시, 정확한 JSON 경로/중첩 codec 또는 literal span, 표시 역할과 적용 전 원문이 모두 맞아야 한다. JS 표현식 전체를 자연어로 번역하지 않는다.

## 기존 도구에서 재사용한 원칙과 차이

기존 AGENTS 및 catalog/tokens/validation을 읽었다. 명시적 표시 필드 선택, 중복 JSON 키 거부, 102/402 동기화, 제어코드 순서 보존, 허용 위치 외 변경 거부를 재사용한다.

기존 선택기는 일본어 포함 여부와 기존 게임 전용 122/356 표시 명령을 포함한다. 검증기는 해당 프로젝트의 plugin/runtime/exposed-notes 모듈에 결합돼 있다. 이를 import한 뒤 전역 predicate를 바꾸거나 monkeypatch하지 않는다. 이번 영어 원본에 맞춘 언어 판별·확인된 core allowlist·별도 plugin 계약을 작은 모듈로 구현한다. 예전 코드나 설정은 변경하지 않는다.

## 적용과 검증 경계

적용 대상 경로는 명시 입력이며 원본과 같거나 원본 내부인 경로를 거부한다. 원본 자산 복사와 native runtime 구성은 다른 담당자의 일이다. 카탈로그 적용은 표시 문자열만 바꾸고 숫자·배열 길이·키·분기·스크립트·메모 등 나머지 JSON 값을 재귀 비교한다. 허용되지 않은 차이가 하나라도 있으면 성공 보고서를 만들지 않는다.

번역 입력·shard·원본·자산·게임 앱은 공개 저장소에 넣지 않는다. 실패 시 원문·빈 문자열로 조용히 대체하지 않는다. 내부 구현을 mock하지 않고 합성 MV 자료의 출력·실패·부수 효과를 검사하며, 실제 원본 카탈로그의 재현성과 해시도 확인한다.
