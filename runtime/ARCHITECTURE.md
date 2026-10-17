# Peasant’s Quest NYD412 macOS 런타임 경계

## 입력과 보존

- 원본 `www/`와 루트 `package.json`은 읽기 전용이다.
- 카탈로그·번역 적용은 `pq_catalog` 담당이다. 런타임은 그 패키지를 import하지 않으며 `--www`로 지정된 사본만 읽는다.
- 출력은 새 앱 경로만 허용한다. 기존 출력, 입력과 겹치는 경로, 게임 입력의 symlink는 오류다.
- 게임 JS·이미지·오디오·영상·데이터는 바이트 그대로 복사한다. 런타임 진입을 위한 `index.html` 한 곳과 앱용 루트 manifest만 별도 변경 기록에 남긴다.

## 단일 기준

- `runtime-lock.json`: NW.js 버전·공식 URL·SHA-256, 앱 ID·프로필 이름·표시 이름, 폰트·OFL 해시.
- `addin.js`: 게임 저장 경로 변경의 유일한 구현. 기존 `StorageManager`의 저장·로드·백업 방식과 압축 형식은 유지한다.
- `font-fallback.js`: 모든 플러그인 로드 후 최종 `Bitmap._makeFontNameText`를 감싼다. 원래 폰트 선택·bold·italic·크기와 측정/출력의 공통 경로를 보존한다.
- 원본 파일 manifest: `schema`, `root_package_sha256`, `www_files`, `file_count`, `bytes`. `pq_catalog`는 이 manifest와 SHA leaf만 소비한다.
- 빌드 보고서: 입력 파일별 SHA-256, 허용된 변경, 추가 파일, 사용한 런타임의 SHA-256.

## 의존 방향

`build_cli.py → runtime.bundle → runtime.{archive,files,config}`

`runtime.archive → runtime.shared.archive → runtime.shared.hygiene`

`runtime.bundle → runtime.shared.native`

`runtime.qa → runtime.files`

`runtime.media → runtime.media_references`, `runtime.shared.asset_crypto`

공용 `mac_release`의 `native.py`, `hygiene.py`, `archive.py`와 기존 `noel_localizer.asset_crypto`는 변경 없는 스냅샷으로 재사용한다. 해시는 `shared/PROVENANCE.json`에 둔다. 개인 작업 경로를 import 경로에 추가하지 않는다. 통합 저장소에 같은 공용 패키지가 들어가면 중복 스냅샷을 제거하고 그 패키지로 의존을 옮긴다. `runtime.shared.archive.sha256_file`은 stdlib와 하위 hygiene만 의존하며 빌드 초기화가 없다.

## 실행과 저장

- 압축하지 않은 `Contents/Resources/app.nw/www`를 사용한다. 게임의 임시 경로 부팅 차단 조건을 우회하지 않는다.
- 모든 원본 플러그인이 로드된 뒤, 기존 `window.onload`가 부팅을 시작하기 직전에 addin을 설치한다.
- NW.js의 고유 manifest `name`으로 브라우저 프로필을 분리한다. 게임 세이브도 그 프로필의 전용 하위 폴더로 보낸다. 기존 세이브를 자동 탐색하거나 가져오지 않는다.
- macOS/arm64 실행과 예상한 게임 저장 API가 아니면 명시적으로 오류를 낸다. 원래 저장 경로로 되돌아가는 fallback은 없다.
- 조립은 물리 임시 폴더에서 수행한다. 기본 build는 서명·검증 후 복사하고 목적지에서도 다시 검증한다. FileProvider 목적지에서 실패하면 오류로 종료한다.
- `--prepare-only`는 별도로 선택하는 구성 검사용 모드다. 서명을 수행하지 않으며 보고서에 `signature_verified=false`를 기록한다. 최종 번역 적용 뒤 물리 배포 사본에서 서명·ZIP 검증이 필요하다.
- 이번 단계는 GUI·renderer를 실행하지 않는다. 정적 arm64 검사, 서명 검사, Node 기반 파일 저장 행동 검사가 화면·미디어·입력 호환성을 증명하지는 않는다.
