# ATmega4809 UPDI Programmer

Windows에서 SerialUPDI 방식으로 ATmega4809를 연결하고, 펌웨어와 fuse/lock bit를 관리하는 Tkinter 기반 GUI 도구입니다.

일반 개발 작업과 양산 작업을 분리해서 제공합니다. 일반 기능은 개별 명령으로 실행할 수 있고, 양산 기능은 JSON Production Profile을 기준으로 펌웨어 무결성과 설정값을 검증한 뒤 정해진 순서대로 자동 수행합니다.

상세한 설치 및 작업 절차는 [사용자 매뉴얼](docs/USER_MANUAL.md)을 참고하십시오.

## 주요 기능

- Windows COM 포트 검색 및 선택
- ATmega4809 device signature 확인 (`0x1e9651`)
- Intel HEX 파일 선택 및 SHA-256 자동 계산
- Flash write 및 verify
- 독립적인 Chip Erase 실행
- Fuse 및 lock bit 읽기/쓰기
- AVRDUDE 로그 실시간 표시
- 별도 JSON 파일 기반 양산 설정
- Profile과 펌웨어 SHA-256 대조
- Fuse 예약 비트 검사
- 양산 순서 자동화
  - Signature 확인
  - Chip Erase
  - Flash write/verify
  - Fuse write/read-back verify
  - Lock bit 마지막 write/read-back verify
- `READY`, `RUNNING`, `PASS`, `FAIL` 양산 상태 표시
- PyInstaller 기반 단일 Windows 실행파일 생성

## 지원 환경

| 항목 | 내용 |
| --- | --- |
| 운영체제 | Windows 10/11 권장 |
| 대상 MCU | ATmega4809 |
| 프로그래머 | AVRDUDE `serialupdi` |
| 기본 통신 속도 | 115200 baud |
| 펌웨어 형식 | Intel HEX (`.hex`) |
| GUI | Python Tkinter |
| 테스트한 Python | Python 3.13 |

현재 코드는 ATmega4809와 `serialupdi`에 맞춰져 있습니다. 다른 MCU나 프로그래머를 사용하려면 device signature, fuse 목록, fuse mask 및 AVRDUDE 옵션을 함께 검토해야 합니다.

## 빠른 시작

배포 환경에는 다음 파일을 준비합니다.

```text
production/
  ATmega4809_UPDI_Programmer.exe
  production_profile.json
  firmware.hex
```

1. 대상 보드의 전원, GND, UPDI 신호를 연결합니다.
2. `ATmega4809_UPDI_Programmer.exe`를 실행합니다.
3. `Refresh`를 누르고 SerialUPDI 어댑터의 COM 포트를 선택합니다.
4. 일반 작업은 HEX 파일을 선택한 뒤 `Program HEX`를 누릅니다.
5. 양산 작업은 JSON Profile을 선택한 뒤 `Production Program`을 누릅니다.
6. 양산 결과가 `PASS`인지 확인합니다.

UPDI 어댑터의 회로와 신호 방향은 사용 중인 하드웨어 설계에 따라 다릅니다. 대상 보드와 어댑터는 반드시 GND를 공유해야 하며, 대상 전압과 어댑터 I/O 전압이 호환되어야 합니다.

## 일반 기능과 양산 기능

### 일반 기능

다음 기능은 Production Profile과 무관하게 독립적으로 동작합니다.

- `Check Connection`: ATmega4809 연결 및 signature 확인
- `Chip Erase`: Flash 내용을 단독 삭제
- `Program HEX`: 선택한 HEX 파일을 Flash에 기록
- `Verify`: 일반 Flash writing 후 verify 사용 여부
- `Read Fuses`: Fuse와 lock bit 읽기
- `Write Checked Fuses`: 체크한 항목만 쓰기

일반 `Program HEX`는 Profile이 선택되어 있어도 fuse, lock bit 또는 Chip Erase를 자동 실행하지 않습니다.

### 양산 기능

`Production Program`은 선택한 JSON Profile만 사용합니다. Profile의 firmware 파일명과 SHA-256이 실제 HEX 파일과 일치해야 시작할 수 있습니다.

```text
Profile validation
  -> Device signature
  -> Chip Erase (profile option)
  -> Flash write/verify
  -> Fuse write/read-back verify
  -> Lock bit write/read-back verify (last)
  -> PASS or FAIL
```

## Production Profile

예제는 [production_profile.json](production_profile.json)에 있습니다.

```json
{
  "profile_name": "900MHz Transmitter Production v1.0",
  "device": "m4809",
  "signature": "1e9651",
  "chip_erase": true,
  "verify_flash": true,
  "firmware": {
    "file": "hw_test.hex",
    "sha256": "7968cb2b7218d19b695d270b4ee602250a20c1498c60f818c2245e593e1a1bf1"
  },
  "fuses": {
    "fuse0": "0x00",
    "fuse1": "0x00",
    "fuse2": "0x02",
    "fuse5": "0xe4",
    "fuse6": "0x07",
    "fuse7": "0x00",
    "fuse8": "0x00"
  },
  "lock": "0xc5"
}
```

Profile의 상대 firmware 경로는 Profile JSON 파일이 있는 폴더를 기준으로 해석됩니다. Profile에 없는 fuse는 양산 작업에서 변경하지 않습니다. Lock bit는 설정된 경우 항상 마지막에 처리됩니다.

현재 예제 fuse 및 lock 값은 프로젝트에서 사용하던 보드의 값을 기반으로 합니다. 실제 양산 사양으로 확정하기 전에 회로, clock, BOD, watchdog, boot 영역 및 보안 정책과 일치하는지 검토해야 합니다.

## SHA-256 계산

HEX가 변경되면 Profile의 SHA-256도 반드시 갱신해야 합니다.

PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 .\firmware.hex
```

프로그램에서 HEX 파일을 선택하면 Files 영역의 `SHA-256` 필드에도 같은 값이 표시됩니다.

## 소스 실행

필수 파일:

```text
updi_programmer.py
avrdude.exe
avrdude.conf
```

실행:

```powershell
python .\updi_programmer.py
```

Python 표준 라이브러리만 사용하며 GUI에는 Tkinter가 필요합니다.

## 실행파일 빌드

PyInstaller를 설치합니다.

```powershell
python -m pip install pyinstaller
```

`build_exe.ps1`의 `$python` 경로를 현재 PC의 Python 설치 경로에 맞게 수정한 뒤 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

결과:

```text
dist\ATmega4809_UPDI_Programmer.exe
```

빌드된 exe에는 `avrdude.exe`, `avrdude.conf`, Python 및 Tkinter 런타임이 포함됩니다. Production Profile과 HEX 파일은 제품별 변경이 가능하도록 exe 외부에서 관리합니다.

### PyInstaller 런타임 폴더

단일 exe는 실행할 때 exe 실행 위치에 `_MEI...` 런타임 폴더를 생성합니다. 프로그램은 UI를 표시하기 전에 다음 정리를 수행합니다.

- 현재 실행에 사용하는 `_MEI...` 폴더에 Windows Hidden 속성 적용
- 현재 실행 폴더는 삭제 대상에서 제외
- exe 폴더 바로 아래의 `_MEI*`만 검색
- 1시간 이상 지난 잔여 폴더만 삭제
- 다른 인스턴스나 보안 프로그램이 사용 중인 폴더는 건너뜀

정상 종료 시 현재 런타임 폴더는 PyInstaller가 자동 삭제합니다. 비정상 종료로 폴더가 남아도 다음 실행에서 1시간이 지난 뒤 자동 정리 대상이 됩니다. Windows 탐색기에서 숨김 항목 표시가 켜져 있으면 Hidden 폴더도 보일 수 있습니다.

## 저장소 구조

```text
updi_tool/
  updi_programmer.py                         GUI 및 프로그래밍 로직
  avrdude.exe                     AVRDUDE 실행파일
  avrdude.conf                    ATmega4809/serialupdi 설정
  production_profile.json         양산 Profile 예제
  hw_test.hex                     예제 또는 현재 펌웨어
  build_exe.ps1                   단일 exe 빌드 스크립트
  docs/
    USER_MANUAL.md                상세 사용자 매뉴얼
  dist/                           빌드 결과물
  build/                          PyInstaller 임시 생성물
```

`build/`, `dist/`, `__pycache__/`, `_MEI*/`는 일반적으로 소스 관리에서 제외하는 것이 좋습니다. 펌웨어와 Production Profile은 회사의 배포 및 변경관리 정책에 따라 별도 저장소나 Release artifact로 관리할 수 있습니다.

## 안전 주의사항

- Fuse 값은 clock, BOD, watchdog, reset 및 boot 동작을 바꿀 수 있습니다.
- Lock bit는 읽기/쓰기 보호에 영향을 주므로 항상 검증된 값만 사용하십시오.
- Lock bit는 양산 순서의 마지막에 기록합니다.
- Chip Erase는 대상 Flash 내용을 삭제합니다.
- 잘못된 Profile과 HEX 조합은 SHA-256 검사에서 차단됩니다.
- 작업 전 대상 전압과 UPDI 배선을 확인하십시오.
- 양산 투입 전 기준 샘플로 전체 절차를 검증하십시오.

## 제3자 구성요소

이 프로젝트는 AVRDUDE 실행파일과 설정 파일을 함께 배포할 수 있습니다. GitHub 공개 또는 실행파일 재배포 전 AVRDUDE의 라이선스, 저작권 고지 및 소스 제공 의무를 확인하고 저장소에 적절한 라이선스 문서를 포함하십시오.

프로젝트 자체의 라이선스도 공개 범위에 맞춰 별도의 `LICENSE` 파일로 지정하는 것을 권장합니다.

## 문제 해결

대표적인 오류와 조치:

| 증상 | 확인 사항 |
| --- | --- |
| COM 포트가 보이지 않음 | USB 연결, 드라이버, `Refresh` 실행 |
| COM 포트를 열 수 없음 | 다른 터미널/IDE가 포트를 점유하는지 확인 |
| UPDI link initialization failed | 전원, GND, UPDI 배선, 어댑터 방향, baud rate 확인 |
| Signature mismatch | MCU 모델과 Profile의 `device`, `signature` 확인 |
| SHA-256 mismatch | HEX를 다시 계산하고 Profile 갱신 |
| Fuse verify 실패 | 예약 비트, 대상 전원 안정성, Profile 값 검토 |
| exe 실행 시 임시 폴더 오류 | 쓰기 가능한 폴더에서 exe 실행, 실행 중인 다른 인스턴스 확인 |

더 자세한 절차는 [사용자 매뉴얼](docs/USER_MANUAL.md)의 문제 해결 항목을 참고하십시오.
