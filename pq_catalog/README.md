# RPG Maker MV 표시 문구 카탈로그

Python 3.11 이상으로 원본의 표시 위치를 추출하고, 직접 번역용 입력을 나누고, 완성된 번역을 별도 `www` 사본에 적용한다. 모델·번역 서버를 호출하지 않는다. 원본 복사·macOS 런타임·폰트·세이브 격리는 `runtime` 경계가 담당한다.

명령은 저장소 루트에서 실행한다. `LOCALIZATION_SOURCE_WWW`는 읽기 전용 원본 `www`, `LOCALIZATION_PRIVATE_PROJECT`는 저장소 밖의 비공개 작업 폴더를 지정한 환경 변수다. 원본·실제 카탈로그·용어집·입력·번역·적용 결과는 이 저장소에 두지 않는다.

```sh
python3 -B -m pq_catalog.cli build-core \
  --www "$LOCALIZATION_SOURCE_WWW" \
  --source-manifest "$LOCALIZATION_PRIVATE_PROJECT/quality/source-manifest.json" \
  --glossary "$LOCALIZATION_PRIVATE_PROJECT/translation/glossary.json" \
  --project "$LOCALIZATION_PRIVATE_PROJECT"
```

원본 manifest의 `www_files`는 상대 파일명→SHA-256 객체다. 용어집의 `machine_preserves`는 `{file,path,source,reason}` 배열이며 원문 경로 guard가 틀리면 실패한다. 추출 당시 용어집 전체 해시는 출처 기록이다. 용어 추가 후 재실행할 때 선택 결과·원문 유지 규칙이 같으면 이미 고정한 코어 파일을 그대로 보존한다.

코어 입력은 `translation/inputs/group-N/core/`, 번역은 `translation/group-N/*.json`에 저장한다. shard는 `{"id":"한국어"}` 객체이며 입력·보고서를 shard 폴더에 섞지 않는다. 문맥은 같은 이벤트 페이지의 표시 명령 인덱스로 제공한다. 그룹은 이벤트를 나누지 않으며, 입력은 최대 180문구·문맥 포함 2,500영단어다.

감사된 플러그인 표시 문구는 별도 입력으로 붙인다. 기존 코어 ID·분담·입력 바이트는 바꾸지 않는다.

```sh
python3 -B -m pq_catalog.cli add-plugins \
  --www "$LOCALIZATION_SOURCE_WWW" \
  --source-manifest "$LOCALIZATION_PRIVATE_PROJECT/quality/source-manifest.json" \
  --glossary "$LOCALIZATION_PRIVATE_PROJECT/translation/glossary.json" \
  --audit-spec "$LOCALIZATION_PRIVATE_PROJECT/quality/plugin-audit-display-spec.json" \
  --project "$LOCALIZATION_PRIVATE_PROJECT"
python3 -B -m pq_catalog.cli validate --project "$LOCALIZATION_PRIVATE_PROJECT" --group 1 --pending 100
python3 -B -m pq_catalog.cli validate --project "$LOCALIZATION_PRIVATE_PROJECT" --group 1 --require-complete
```

`--phase core` 또는 `--phase additions`로 범위를 좁힐 수 있다. 기본값은 전체다. 검증은 ID·중복·빈 번역·제어코드·숫자·개행을 다루며 의미와 자연스러움은 별도 교열이 필요하다. 이름창 `\n<Name>`의 표시 payload는 번역하되 껍질은 보존한다. 전투 메시지 조각의 결합 방식과 보호된 템플릿 표현식은 입력의 문맥·`protected`를 따른다.

모든 그룹이 완성된 뒤 준비된 별도 사본을 명시한다. 플러그인 JS를 적용할 때 Node의 `--check`로 구문만 검사한다. `--node`로 로컬 실행 파일을 지정할 수 있다.

```sh
python3 -B -m pq_catalog.cli apply \
  --project "$LOCALIZATION_PRIVATE_PROJECT" \
  --source-www "$LOCALIZATION_SOURCE_WWW" \
  --target-www "$LOCALIZATION_TARGET_WWW" \
  --audit-spec "$LOCALIZATION_PRIVATE_PROJECT/quality/plugin-audit-display-spec.json"
```

원본과 겹치는 대상, 미완성 번역, 어긋난 baseline, 감사 계약 불일치는 쓰기 전에 거절한다. 변경할 파일은 전부 준비·검사한 뒤 잠금을 잡아 교체하며 교체 중 예외에는 이미 바꾼 파일을 복구하고 오류를 다시 알린다. 표시 위치 밖 JSON 값과 중첩 플러그인 값은 재귀 비교한다. 일반 JS는 감사된 리터럴 밖 바이트와 계산식을 보존하고, 플러그인 JSON 배열은 모든 비표시 값을 보존한다. 파일 해시 검사는 선언된 데이터·JS만 다루며 런타임이 추가한 파일 전체를 동일 집합으로 강제하지 않는다.

합성 자료 검증과 타입 검사:

```sh
python3 -B -m unittest discover -s tests/catalog -v
python3 -m mypy --strict --follow-imports=silent --python-version 3.11 pq_catalog
```

타입 검사 도구는 `mypy==1.18.2`다. 합성 자료 테스트는 실제 게임의 실행·번역 품질을 검증하지 않는다. 원본을 사용한 적용 검사와 게임 GUI 검수는 비공개 작업 폴더에서 별도로 수행한다. 모듈·의존 방향은 [ARCHITECTURE.md](ARCHITECTURE.md)를 따른다.
