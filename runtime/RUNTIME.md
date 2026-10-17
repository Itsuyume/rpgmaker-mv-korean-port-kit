# Peasant’s Quest NYD412 런타임 준비

Python 표준 라이브러리와 macOS 기본 도구로 원본을 보존한 NW.js arm64 앱 사본을 만든다. 이 도구는 번역이나 게임 실행을 시작하지 않는다. `runtime-lock.json`의 공식 NW.js 0.117.0 ZIP과 Noto Sans CJK KR/OFL 파일을 별도 입력으로 제공해야 한다. 바이너리·게임·실제 원본 manifest·개인 저장 데이터는 소스 저장소에 넣지 않는다.

## 순서

아래 변수는 각자의 로컬 경로로 지정한다. 출력 폴더는 미리 만들고, 앱·보고서 경로는 새 경로를 사용한다. 임시 조립에는 게임과 런타임을 합친 크기 이상의 여유 공간이 필요하다.

```sh
python3 -B "$KIT/build_cli.py" snapshot \
  --www "$GAME/www" --package "$GAME/package.json" \
  --out "$QA/source-manifest.json"

python3 -B "$KIT/build_cli.py" build --prepare-only \
  --www "$GAME/www" --package "$GAME/package.json" \
  --manifest "$QA/source-manifest.json" \
  --runtime-zip "$VENDOR/nwjs-v0.117.0-osx-arm64.zip" \
  --font "$VENDOR/NotoSansCJKkr-Regular.otf" --font-license "$VENDOR/OFL.txt" \
  --out-app "$STAGE/PeasantsQuest-NYD412-Native.app" \
  --report "$QA/runtime-build-report.json"

python3 -B "$KIT/qa_cli.py" --prepare-only \
  --app "$STAGE/PeasantsQuest-NYD412-Native.app" \
  --build-report "$QA/runtime-build-report.json" --out "$QA/runtime-static-qa.json"
```

`--prepare-only`의 성공은 구성·자산 해시·arm64 검사 결과다. 서명·부팅·저장 UI·미디어 재생을 확인했다는 뜻이 아니다. 원본 대비 변경은 `index.html` 한 곳, 추가는 `mac/` 아래 코드·CSS·폰트·OFL 다섯 파일이다. 원래 `save/`는 비어 있을 때만 제외하며 데이터가 있으면 빌드가 실패한다.

카탈로그 적용 대상은 앱의 `Contents/Resources/app.nw/www`다. 런타임 overlay를 만든 뒤, 카탈로그가 검사한 원본 JSON/JS에 번역을 적용한다. 번역 적용으로 해시가 바뀌므로 기존 runtime build 보고서를 최종 번역 사본의 전체 해시 기준으로 재사용하면 안 된다. 통합 담당자가 적용 보고서의 허용 변경과 자산 해시를 확인한 뒤 최종 manifest를 만든다. 번역된 별도 `www`를 새 build 입력으로 쓰는 경우에도 그 입력과 정확히 일치하는 새 snapshot이 필요하다.

## 서명과 최종 패키징

기본 build는 `--prepare-only` 없이 실행하면 물리 임시 사본을 조립·ad-hoc 서명·검증하고, 목적지 복사 후에도 strict 검증한다. 목적지에서 서명 검증이 실패하면 그대로 실패한다. Documents의 FileProvider가 가상 FinderInfo를 붙이는 경우 stage는 준비본으로만 두고 최종 packager가 물리 배포 폴더의 정상 사본을 서명해야 한다. 보안 설정 변경이나 묵시적인 서명 생략은 없다.

최종 서명은 번역·아이콘 등 모든 변경 뒤에 한다. ZIP 생성·추출 후 다시 서명/해시를 검증하고 그 최종 사본으로 사람이 부팅·저장/불러오기·한글 표시·영상/음성을 확인한다. 최종 사본이 번역 전 build 보고서와 달라졌다면 그 보고서로 `qa_cli`의 전체 해시 일치를 주장하지 않는다.

이 핀의 공식 원본 root와 18개 Mach-O에는 entitlement가 없고 `adhoc,linker-signed` 플래그가 있었다. 실제 deep ad-hoc 서명에서 entitlement는 그대로 없으며 root와 15개 Mach-O의 linker-signed 표시만 사라졌다. 이 결과를 Hardened Runtime/Developer ID/MAS 빌드 일반에 적용하지 않는다. [NW.js 공식 서명 문서](https://docs.nwjs.io/For%20Users/Advanced/Support%20for%20Mac%20App%20Store/)는 해당 인증서와 parent/child entitlement 설정을 별도로 다룬다.

## 저장과 글꼴

프로필 이름은 `peasants-quest-nyd412-ko-native-v1`이다. 세이브는 NW.js `App.dataPath` 아래 `rpg-save-nyd412-v1/`에만 생성한다. 앱 내부 경로와 앱 내부로 연결된 심볼릭 링크는 거절한다. 기존 세이브를 찾거나 가져오지 않는다. `mainModule` 또는 예상 API가 없으면 명시적으로 시작 오류를 낸다.

추가 폰트는 원래 선택된 영문 폰트 다음, `sans-serif` 같은 일반 fallback 이전에 들어간다. SRD 옵션의 선택 별칭·HUD·YEP bold 경로도 최종 Bitmap 함수에서 처리한다. 원작의 글자 크기와 대사 창 크기는 바꾸지 않는다. CoreText 글리프/너비 검사는 브라우저의 실제 줄바꿈과 잘림 검사를 대신하지 않는다.

한글 이름이 있는 이름 편집창은 실제 한글 글자 너비를 사용하며, 초상화 옆에 입력칸이 들어가도록 해당 창만 넓힌다. 라틴 문자만 있는 이름의 기존 배치는 유지한다. 원본 199개 이름 입력 명령은 모두 최대 12자로 확인했다. 이름의 내용·허용 글자 수·행위자 ID는 변경하지 않는다.

## 미디어와 독립 검증

```sh
python3 -B "$KIT/media_cli.py" --www "$GAME/www" \
  --ffprobe "$FFPROBE" --ffmpeg-library "$OFFICIAL_LIBFFMPEG" \
  --temporary-parent "$QA" --out "$QA/media-runtime-report.json"

python3 -B -m unittest discover -s "$KIT/runtime/tests" -p 'test_*.py' -v
node --test "$KIT/runtime/tests/storage.test.js" "$KIT/runtime/tests/font.test.js"
```

미디어 검사는 메타데이터만 읽고 암호화 오디오는 검사 중 임시 사본만 복호화한 뒤 삭제한다. 파일 누락과 codec 등록 결과를 기록하며 재생·재인코딩하지 않는다. VP8/VP9는 Chromium의 별도 VpxVideoDecoder 경로가 있으므로 libffmpeg 등록 목록만 보고 지원 불가라고 결론 내리지 않는다. 실제 WebM/Ogg의 `canPlayType` 및 재생은 실행 검수 대상이다.

모듈은 키트 바깥 cwd에서도 동작한다. 빌드 코드는 게임 파일이나 상위 workspace를 import하지 않으며 SHA·ZIP·복사 구현의 공용 출처는 `ARCHITECTURE.md`와 `shared/PROVENANCE.json`에 적혀 있다.

[공식 0.117.0 릴리스](https://nwjs.io/blog/v0.117.0/), [배포 구조](https://docs.nwjs.io/For%20Users/Package%20and%20Distribute/), [manifest](https://docs.nwjs.io/References/Manifest%20Format/), [App.dataPath](https://docs.nwjs.io/References/App/), [Node 변경점](https://docs.nwjs.io/References/Changes%20to%20Node/).
