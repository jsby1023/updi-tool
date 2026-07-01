# ATmega4809 UPDI Programmer 사용자 매뉴얼

## 1. 문서 목적

이 문서는 ATmega4809 UPDI Programmer를 사용하여 다음 작업을 수행하는 방법을 설명합니다.

- ATmega4809 연결 확인
- HEX 펌웨어 기록 및 검증
- Chip Erase
- Fuse와 lock bit 읽기/쓰기
- JSON Production Profile을 이용한 양산 자동 프로그래밍
- 오류 로그 확인 및 문제 해결

이 도구는 Windows와 SerialUPDI 환경을 기준으로 합니다. 현재 대상 MCU는 ATmega4809로 고정되어 있습니다.

## 2. 중요한 안전 수칙

작업 전에 다음 내용을 반드시 확인하십시오.

1. 대상 보드와 UPDI 어댑터의 GND를 공통으로 연결합니다.
2. 대상 MCU 전원 전압과 어댑터 I/O 전압이 호환되는지 확인합니다.
3. UPDI 신호 방향과 어댑터 회로를 확인합니다.
4. 다른 터미널이나 프로그램이 동일 COM 포트를 사용하지 않도록 합니다.
5. Fuse와 lock bit는 승인된 Production Profile 또는 설계값만 사용합니다.
6. Chip Erase는 대상 Flash 내용을 삭제합니다.
7. Lock bit는 보호 설정에 영향을 주므로 양산 절차의 마지막에 기록합니다.
8. 새 Profile은 기준 샘플 보드에서 검증한 후 양산에 적용합니다.

잘못된 fuse 설정은 clock, BOD, watchdog, reset 또는 boot 동작을 변경할 수 있습니다. 잘못된 lock bit는 읽기, 쓰기 또는 재작업을 제한할 수 있습니다.

## 3. 준비물

### 3.1 하드웨어

- ATmega4809 대상 보드
- SerialUPDI 호환 USB-Serial 어댑터 또는 프로그래머
- UPDI 연결 회로
- 대상 보드 전원
- USB 케이블

SerialUPDI 어댑터의 회로 구성은 제품별로 다를 수 있습니다. 본 프로그램은 COM 포트로 AVRDUDE `serialupdi` programmer를 호출하며, 하드웨어 신호 변환 회로 자체는 제공하지 않습니다.

### 3.2 양산 배포 파일

권장 배포 구조:

```text
production/
  ATmega4809_UPDI_Programmer.exe
  production_profile.json
  product_firmware.hex
```

- 실행파일에는 AVRDUDE와 Python/Tkinter 런타임이 포함됩니다.
- Production Profile과 HEX는 제품 및 버전별 변경을 위해 외부 파일로 관리합니다.
- Profile과 HEX는 같은 폴더에 두는 것이 가장 단순합니다.

## 4. 프로그램 시작

1. `ATmega4809_UPDI_Programmer.exe`를 실행합니다.
2. Windows 보안 경고가 표시되면 회사 정책에 따라 실행 허용 여부를 확인합니다.
3. SerialUPDI 어댑터를 PC에 연결합니다.
4. 대상 보드에 전원을 공급합니다.
5. Program 탭의 `Refresh`를 누릅니다.
6. 표시된 COM 포트에서 SerialUPDI 어댑터의 포트를 선택합니다.

처음 실행했을 때 양산 상태 표시는 `READY`입니다. `READY`는 버튼이 아니라 Production 작업 대기 상태입니다.

## 5. 화면 구성

### 5.1 Program 탭

### Files 영역

| 항목 | 설명 |
| --- | --- |
| HEX File | 일반 또는 양산에 사용할 Intel HEX 파일 |
| SHA-256 | 선택한 HEX 내용을 기준으로 자동 계산한 해시 |
| Profile | 양산 작업에 사용할 JSON Production Profile |
| Profile name | Profile을 검증한 뒤 표시되는 제품/버전 이름 |

HEX 파일을 Browse로 선택하거나 Profile이 HEX를 자동 지정하면 SHA-256이 계산됩니다. 파일 내용이 변경되면 해시도 변경됩니다.

### Connection 영역

| 항목 | 설명 |
| --- | --- |
| Port | SerialUPDI 어댑터 COM 포트 |
| Refresh | Windows COM 포트 목록 다시 검색 |
| Baud | UPDI 통신 속도 |
| Verify | 일반 `Program HEX` 작업의 write 후 verify 여부 |

기본 baud rate는 115200입니다. 연결이 불안정할 경우 `Check Connection`은 더 낮은 baud rate도 순서대로 시도합니다.

### 작업 버튼

| 버튼 | 설명 |
| --- | --- |
| Check Connection | Signature를 읽어 ATmega4809 연결 확인 |
| Chip Erase | Flash 내용을 단독 삭제 |
| Program HEX | 선택한 HEX만 기록 |
| Production Program | Profile에 정의된 양산 전체 절차 실행 |

### 양산 상태

| 상태 | 의미 |
| --- | --- |
| READY | Production 작업 전 대기 상태 |
| RUNNING | Production 작업 진행 중 |
| PASS | 모든 양산 단계 성공 |
| FAIL | Profile 검증 또는 작업 단계 실패 |

일반 `Program HEX`, `Chip Erase`, fuse 작업은 이 양산 상태의 의미를 변경하지 않습니다.

### Log 영역

AVRDUDE 명령과 결과가 실시간으로 표시됩니다. 오류 발생 시 마지막 단계명, AVRDUDE 오류 문구 및 exit code를 확인합니다.

### 5.2 Fuses 탭

지원하는 메모리:

| Memory | 이름 | 주요 용도 |
| --- | --- | --- |
| fuse0 | WDTCFG | Watchdog 설정 |
| fuse1 | BODCFG | Brown-out detector 설정 |
| fuse2 | OSCCFG | Oscillator 설정 |
| fuse5 | SYSCFG0 | 시스템 설정 0 |
| fuse6 | SYSCFG1 | 시스템 설정 1 |
| fuse7 | APPEND / CODESIZE | Application code 영역 설정 |
| fuse8 | BOOTEND / BOOTSIZE | Boot 영역 설정 |
| lock | LOCKBIT | 읽기/쓰기 보호 설정 |

값은 `0x00`부터 `0xFF` 사이의 1-byte hexadecimal 형식으로 입력합니다. 예: `0x07`, `E4`, `ff`.

`Read Fuses`는 모든 fuse와 lock bit를 읽어 Value 필드에 표시합니다. `Write Checked Fuses`는 Write 열에서 체크한 항목만 기록합니다.

## 6. 연결 확인

1. 대상 보드 전원과 UPDI 배선을 확인합니다.
2. Program 탭에서 COM 포트를 선택합니다.
3. `Check Connection`을 누릅니다.
4. 성공 메시지와 다음 signature를 확인합니다.

```text
device signature = 0x1e9651
```

성공 시 프로그램은 `Connection OK: ATmega4809 detected`를 표시합니다.

연결 실패 시 낮은 baud rate를 자동으로 시도할 수 있습니다. 모든 속도에서 실패하면 전원, GND, UPDI 배선, COM 포트 및 어댑터 방향을 점검합니다.

## 7. 일반 HEX 프로그래밍

일반 작업은 Production Profile과 독립적입니다.

1. `HEX File`의 Browse를 누릅니다.
2. 기록할 `.hex` 파일을 선택합니다.
3. SHA-256이 표시되는지 확인합니다.
4. COM 포트와 baud rate를 확인합니다.
5. write 후 검증이 필요하면 `Verify`를 체크합니다.
6. `Program HEX`를 누릅니다.
7. Log에서 write 및 verify 결과를 확인합니다.
8. 성공 메시지를 확인합니다.

일반 `Program HEX`는 다음 동작을 자동으로 수행하지 않습니다.

- Production Profile 검증
- 별도 Chip Erase
- Fuse 변경
- Lock bit 변경

일반적인 펌웨어 갱신은 먼저 Chip Erase를 누르지 않고 `Program HEX`만 실행해도 됩니다. 전체 Flash 삭제가 명시적으로 필요한 경우에만 `Chip Erase`를 별도로 실행합니다.

## 8. Chip Erase

1. 대상 보드와 COM 포트를 확인합니다.
2. `Chip Erase`를 누릅니다.
3. 경고창의 내용을 읽습니다.
4. 계속하려면 확인합니다.
5. 성공 로그를 확인합니다.

Chip Erase는 Flash 내용을 삭제합니다. 제품 데이터가 Flash에 저장되는 설계라면 삭제 범위를 사전에 검토하십시오.

## 9. Fuse 및 lock bit 수동 작업

### 9.1 읽기

1. Fuses 탭으로 이동합니다.
2. `Read Fuses`를 누릅니다.
3. 각 Value 필드가 채워지는지 확인합니다.
4. Log에서 각 메모리 read 결과를 확인합니다.

Signature 로그의 `0x1e`는 fuse 값이 아닙니다. 프로그램은 한 줄 전체가 1-byte hexadecimal 값인 출력만 fuse 값으로 인식합니다.

### 9.2 쓰기

1. 먼저 `Read Fuses`로 현재 값을 읽습니다.
2. 변경할 행의 Value를 입력합니다.
3. 변경할 행의 Write 체크박스만 선택합니다.
4. `Write Checked Fuses`를 누릅니다.
5. 경고창을 확인합니다.
6. 작업 후 다시 `Read Fuses`를 눌러 값을 비교합니다.

Profile에 없는 fuse나 체크하지 않은 fuse는 변경하지 않습니다.

### 9.3 Lock bit

Lock bit는 fuse와 별도 `lock` 메모리입니다. 보호가 활성화되면 이후 읽기, 쓰기, 검증 또는 재작업에 영향을 줄 수 있습니다.

수동 작업에서도 가능하면 Flash와 fuse 검증을 모두 끝낸 뒤 lock bit를 마지막에 기록하십시오.

## 10. Production Profile 작성

기본 예제:

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

### 10.1 필드 설명

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| profile_name | 예 | 제품명과 생산 버전 |
| device | 예 | 현재 `m4809`만 허용 |
| signature | 예 | ATmega4809는 `1e9651` |
| chip_erase | 예 | 양산 전 Chip Erase 실행 여부 |
| verify_flash | 예 | Flash write 후 verify 여부 |
| firmware.file | 예 | Profile 기준 상대 또는 절대 HEX 경로 |
| firmware.sha256 | 예 | HEX 파일의 64자리 SHA-256 |
| fuses | 예 | 양산에서 기록할 fuse 목록 |
| lock | 아니요 | 양산 마지막에 기록할 lock 값 |

`fuses`에 포함하지 않은 항목은 변경하지 않습니다. 지원하지 않는 fuse 이름이나 예약 비트를 설정한 값은 Profile 검증 단계에서 거부됩니다.

### 10.2 Firmware 상대 경로

다음 구조에서 `firmware.file`은 `firmware/product_v2.hex`로 작성합니다.

```text
release_v2/
  production_profile.json
  firmware/
    product_v2.hex
```

### 10.3 JSON 작성 주의사항

- 문자열은 큰따옴표를 사용합니다.
- 마지막 항목 뒤에는 쉼표를 붙이지 않습니다.
- Boolean은 문자열이 아닌 `true`, `false`를 사용합니다.
- SHA-256은 공백 없는 64자리 hexadecimal 값이어야 합니다.
- Fuse 값은 `0x00`부터 `0xFF` 형식의 문자열 사용을 권장합니다.

## 11. SHA-256 갱신

펌웨어가 다시 빌드되면 파일명이 같아도 SHA-256은 달라집니다. 양산 Profile을 반드시 갱신해야 합니다.

PowerShell에서 계산:

```powershell
Get-FileHash -Algorithm SHA256 .\product_firmware.hex
```

예시 출력:

```text
Algorithm : SHA256
Hash      : 7968CB2B7218D19B695D270B4EE602250A20C1498C60F818C2245E593E1A1BF1
```

Profile 갱신:

```json
"firmware": {
  "file": "product_firmware.hex",
  "sha256": "7968cb2b7218d19b695d270b4ee602250a20c1498c60f818c2245e593e1a1bf1"
}
```

대소문자는 무관하지만 64자리 전체를 정확히 입력해야 합니다. 프로그램에서 HEX를 선택했을 때 표시되는 SHA-256과 Profile 값을 비교할 수 있습니다.

## 12. 양산 프로그래밍 절차

### 12.1 작업 전 준비

1. 승인된 exe, Profile, HEX 버전을 확인합니다.
2. Profile과 HEX를 같은 양산 배포 폴더에 둡니다.
3. 기준 샘플 보드에서 Profile을 검증합니다.
4. 대상 보드 전원과 UPDI 배선을 확인합니다.
5. SerialUPDI 어댑터 COM 포트를 확인합니다.

### 12.2 실행

1. Program 탭의 Profile Browse를 누릅니다.
2. 승인된 `production_profile.json`을 선택합니다.
3. Profile name과 device 표시를 확인합니다.
4. HEX가 자동 선택되는지 확인합니다.
5. 표시된 SHA-256을 확인합니다.
6. COM 포트를 선택합니다.
7. `Production Program`을 누릅니다.
8. 확인창에서 Profile, firmware, fuse 개수 및 lock 값을 확인합니다.
9. 실행을 승인합니다.
10. 상태가 `RUNNING`으로 변경되는지 확인합니다.
11. 작업 중 대상 보드와 USB 케이블을 분리하지 않습니다.
12. 최종 상태를 확인합니다.

### 12.3 자동 실행 순서

```text
1. Profile schema validation
2. Firmware filename validation
3. Firmware SHA-256 validation
4. ATmega4809 signature check
5. Chip Erase (chip_erase=true일 때)
6. Flash write
7. Flash verify (verify_flash=true일 때)
8. 각 fuse write
9. 각 fuse read-back verify
10. Lock bit write
11. Lock bit read-back verify
12. PASS
```

Lock bit는 항상 마지막에 처리됩니다.

### 12.4 판정

`PASS` 조건:

- Profile 형식 정상
- Firmware 파일명 일치
- SHA-256 일치
- ATmega4809 signature 일치
- 요청된 erase/write/verify 성공
- 모든 fuse read-back 값 일치
- Lock bit read-back 값 일치

하나라도 실패하면 `FAIL`입니다. FAIL 보드는 정상 제품과 분리하고 Log의 실패 단계를 기록한 뒤 재작업 절차를 따릅니다.

## 13. 양산 변경관리 권장사항

제품 또는 펌웨어 버전이 변경될 때 다음 항목을 함께 관리하십시오.

```text
Product ID
Hardware revision
Firmware version
HEX filename
HEX SHA-256
Production Profile version
Fuse values
Lock value
Tool executable version
Approval date and approver
```

권장 배포 예:

```text
releases/
  transmitter_v1.0/
    ATmega4809_UPDI_Programmer.exe
    production_profile.json
    transmitter_v1.0.hex
    release_note.txt
```

Profile 파일을 수정한 뒤에는 파일명 또는 `profile_name`의 버전을 올리고 기준 샘플 검증을 다시 수행하십시오.

## 14. 문제 해결

### 14.1 COM 포트가 목록에 없음

확인 순서:

1. USB 케이블을 다시 연결합니다.
2. Windows 장치 관리자에서 포트를 확인합니다.
3. USB-Serial 드라이버 설치 상태를 확인합니다.
4. 프로그램에서 `Refresh`를 누릅니다.
5. 다른 USB 포트를 사용합니다.

### 14.2 Cannot open COM port

가능한 원인:

- 다른 터미널 프로그램이 포트를 사용 중
- IDE serial monitor가 열려 있음
- 선택한 COM 번호가 변경됨
- 어댑터가 분리됨

포트를 사용하는 프로그램을 닫고 `Refresh` 후 다시 선택합니다.

### 14.3 UPDI link initialization failed

확인 항목:

- 대상 보드 전원
- 공통 GND
- UPDI 배선
- TX/RX 또는 어댑터 방향
- 대상 전압과 I/O 전압
- 케이블 길이와 접촉 상태
- baud rate

115200에서 불안정하면 더 낮은 baud rate로 연결을 확인합니다.

### 14.4 Signature mismatch

ATmega4809의 signature는 `0x1e9651`입니다.

다음 내용을 확인합니다.

- 실제 MCU 모델
- Profile의 `device`
- Profile의 `signature`
- UPDI 통신 안정성

### 14.5 Firmware SHA-256 mismatch

Profile이 지정한 HEX와 선택한 HEX 내용이 다릅니다.

1. 올바른 release 폴더인지 확인합니다.
2. Profile의 firmware 파일명을 확인합니다.
3. `Get-FileHash`로 실제 해시를 계산합니다.
4. 승인된 새 펌웨어라면 Profile을 갱신합니다.
5. 승인되지 않은 파일이면 사용하지 않습니다.

해시 검사를 임의로 우회하지 마십시오.

### 14.6 Profile Error

주요 원인:

- JSON 문법 오류
- 필수 필드 누락
- device가 `m4809`가 아님
- signature가 `1e9651`가 아님
- 잘못된 fuse 이름
- `0x00~0xFF` 범위를 벗어난 값
- 예약 비트 설정
- 잘못된 SHA-256 길이

JSON 편집기 또는 formatter로 형식을 확인한 뒤 다시 선택합니다.

### 14.7 Fuse verify 실패

확인 항목:

- Profile의 fuse 값
- 예약 비트 mask
- 대상 전원 안정성
- UPDI 연결 안정성
- MCU 보호 상태
- 작업 중 USB 또는 보드 연결 변경 여부

같은 보드에서 반복 실패하면 FAIL 보드로 분리하고 기준 장비에서 재검사합니다.

### 14.8 Lock verify 실패

Lock 설정은 보호 정책과 연관됩니다. 임의의 다른 값을 반복 기록하지 마십시오. 제품 보안 사양과 ATmega4809 lock bit 정의를 다시 확인합니다.

### 14.9 exe 실행 오류 또는 `_MEI` 임시 폴더 오류

PyInstaller one-file 실행파일은 실행 시 exe가 있는 폴더 아래 임시 `_MEI...` 디렉터리를 사용할 수 있습니다.

- UI가 표시되기 전에 현재 실행용 `_MEI...` 폴더에 Windows Hidden 속성을 적용합니다.
- 현재 실행 중인 `_MEI...` 폴더는 자동 정리 대상에서 제외합니다.
- exe 폴더 바로 아래에서 1시간 이상 지난 `_MEI*` 폴더만 자동 삭제합니다.
- 다른 프로그램이 사용 중이거나 권한이 없는 폴더는 삭제하지 않고 프로그램 실행을 계속합니다.
- 정상 종료 시 현재 실행용 폴더는 PyInstaller가 자동으로 삭제합니다.
- 비정상 종료 직후 남은 폴더는 다른 인스턴스를 보호하기 위해 즉시 삭제하지 않고 1시간 후 정리 대상으로 처리합니다.
- Windows 탐색기의 `숨긴 항목` 옵션이 켜져 있으면 Hidden 속성이 있어도 폴더가 표시됩니다.
- 쓰기 가능한 로컬 폴더에서 실행합니다.
- 읽기 전용 네트워크 드라이브를 피합니다.
- 백신이 임시 DLL 추출을 차단하는지 확인합니다.
- 자동 삭제되지 않는 폴더는 모든 프로그램 인스턴스가 종료됐는지 확인한 뒤 수동 삭제합니다.

## 15. 소스 실행 및 개발자 빌드

### 15.1 소스 실행

필요 파일:

```text
updi_programmer.py
avrdude.exe
avrdude.conf
```

실행:

```powershell
python .\updi_programmer.py
```

### 15.2 PyInstaller 설치

```powershell
python -m pip install pyinstaller
```

### 15.3 빌드 스크립트 설정

`build_exe.ps1`에서 Python 경로를 현재 PC에 맞게 수정합니다.

```powershell
$python = "C:\Path\To\Python313\python.exe"
```

### 15.4 단일 exe 빌드

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

결과:

```text
dist\ATmega4809_UPDI_Programmer.exe
```

빌드 후 다음 검증을 수행하십시오.

1. exe가 실행되는지 확인합니다.
2. COM 포트 Refresh를 확인합니다.
3. Check Connection을 확인합니다.
4. 기준 HEX의 SHA-256 표시를 확인합니다.
5. Profile 로딩을 확인합니다.
6. 기준 샘플에서 Production Program PASS를 확인합니다.

## 16. 양산 작업자 체크리스트

작업 시작 전:

```text
[ ] 승인된 release 폴더인가
[ ] exe/Profile/HEX 버전이 일치하는가
[ ] 대상 제품과 Profile name이 일치하는가
[ ] 전원과 UPDI 배선이 정상인가
[ ] 올바른 COM 포트를 선택했는가
[ ] 표시 SHA-256이 승인 기록과 일치하는가
```

작업 후:

```text
[ ] 최종 상태가 PASS인가
[ ] Log에 verify 실패가 없는가
[ ] PASS/FAIL 제품을 분리했는가
[ ] 생산 이력에 제품/펌웨어/Profile 버전을 기록했는가
```

FAIL 발생 시:

```text
[ ] 보드를 정상 제품과 분리한다
[ ] 실패 단계와 로그를 기록한다
[ ] 임의로 fuse/lock 값을 변경하지 않는다
[ ] 승인된 재작업 절차를 따른다
```

## 17. 지원 및 유지보수

문제 보고 시 다음 정보를 함께 제공하면 원인 분석이 빨라집니다.

- 프로그램 exe 버전 또는 빌드 날짜
- Production Profile 파일
- HEX 파일명과 SHA-256
- 선택한 COM 포트와 baud rate
- 대상 하드웨어 revision
- 전체 Log 내용
- FAIL 단계
- 동일 조건 재현 여부

Profile이나 fuse 값을 공유할 때는 제품 보안 정책과 저장소 공개 범위를 먼저 확인하십시오.
