# Render에 4개 Mock 서비스 배포하기

이 프로젝트의 `render.yaml`은 동일한 Git 저장소에서 **4개 공개 Web Service**를 생성하는 설정입니다. 거래 조회 2개, 그래프 1개, 설명 2개, 유형 분석 1개로 총 6개 API를 제공합니다. 배포 설정을 준비한 상태이며 Render 서비스 생성·공개 배포는 아직 수행하지 않았습니다.

## 1. 프로젝트를 GitHub 저장소에 올리기

새 저장소를 만들고 **`fraudgt-mock-api` 폴더 안의 내용**을 저장소 루트에 올립니다. 저장소 루트에서 다음 항목들이 바로 보여야 합니다.

```text
app/
scripts/
examples/
requirements.txt
requirements.lock.txt
render.yaml
.gitignore
...
```

`.venv`, `.tmp`, `.pytest_cache`, `__pycache__`, 로컬 `.env`는 올리지 않습니다. 현재 워크스페이스 상위 폴더 전체 대신 이 프로젝트를 별도 저장소로 올리면 앞서 만든 다른 프로젝트와 문서가 섞이지 않습니다. Render에 읽기 권한을 연결하면 비공개 GitHub 저장소도 사용할 수 있습니다.

이미 사용 중인 저장소에서 프로젝트가 `fraudgt-mock-api/` 하위 폴더에 있다면, `render.yaml`의 **4개 서비스 각각에** 다음 필드를 추가합니다.

```yaml
rootDir: fraudgt-mock-api
```

이 경우 Blueprint Path도 `fraudgt-mock-api/render.yaml`로 지정합니다. Blueprint 파일 위치와 앱 실행 디렉터리는 별도 설정입니다. [공식 rootDir 안내](https://render.com/docs/monorepo-support)

## 2. Render Blueprint 만들기

1. [Render Dashboard](https://dashboard.render.com/)에 로그인합니다.
2. **New → Blueprint**를 선택합니다.
3. GitHub를 연결하고 위 저장소를 선택합니다.
4. 브랜치를 선택합니다. 프로젝트 내용을 저장소 루트에 올렸다면 Blueprint Path는 기본 `render.yaml`입니다.
5. 아래 네 서비스와 공통 환경변수 그룹이 생성되는지 검토합니다. 모든 서비스의 Compute Plan은 설정 파일에 `free`로 명시했습니다.
6. **Deploy Blueprint**를 누릅니다.
7. 각 서비스의 빌드·배포 로그에서 성공 상태를 확인합니다.

Blueprint 생성 흐름은 [Render 공식 안내](https://render.com/docs/infrastructure-as-code#setup)를 따릅니다. 새 서비스 이름이 기존 작업의 이름과 겹친다면 해당 서비스로 연결되는지 생성 화면에서 확인하고 필요하면 이름을 바꿉니다.

| Render 서비스 이름 | 제공 API | 실행 앱 |
|---|---|---|
| `fraudgt-mock-alerts` | 거래 목록·상세 | `app.entrypoints.alerts:app` |
| `fraudgt-mock-graph` | 주변 그래프 | `app.entrypoints.graph:app` |
| `fraudgt-mock-explanation` | 설명 요청·결과 | `app.entrypoints.explanation:app` |
| `fraudgt-mock-analysis` | 유형 분석 | `app.entrypoints.analysis:app` |

공통 Build Command는 `pip install -r requirements.lock.txt`입니다. 검증한 Python 버전 `3.13.7`도 공통 환경변수로 고정했습니다. [Python 버전 설정](https://render.com/docs/python-version)

각 Start Command는 다음 형식이며 실제 앱 이름은 `render.yaml`에 각각 설정되어 있습니다.

```sh
python -m uvicorn app.entrypoints.alerts:app --host 0.0.0.0 --port $PORT --workers 1
```

Render에는 각 서비스를 독립적으로 실행합니다. 로컬 일괄 실행기 `scripts/run_services.py`를 Start Command에 넣지 않습니다. 로컬의 8001~8004 포트 대신 Render가 주는 `$PORT`에 바인딩합니다. [공식 FastAPI 배포 안내](https://render.com/docs/deploy-fastapi)

## 3. 배포된 주소 확인과 API 호출

각 Render 서비스 화면에 표시되는 실제 **HTTPS 주소**를 복사합니다. 이름 충돌 등으로 주소에 접미사가 붙을 수 있으므로 파일의 서비스 이름으로 URL을 추측하지 않습니다. URL에 로컬 포트 번호를 붙이지 않습니다.

각 주소 뒤에 `/docs`를 붙이면 해당 서비스의 Swagger가 열립니다. 먼저 4개 Swagger를 모두 열고 실제 API 목록이 표시되는지 확인합니다. Render의 Git 배포 Web Service는 배포 후 `onrender.com` 주소를 제공합니다. [Web Service 안내](https://render.com/docs/web-services)

거래 조회 서비스 Swagger에서 `GET /api/alerts`를 다음 기간으로 호출합니다.

```text
start = 2022-11-01T00:00:00Z
end   = 2022-11-02T00:00:00Z
```

그다음 같은 `TX000003`을 각 서비스에 전달합니다.

```text
alerts 주소      + /api/alerts/TX000003
graph 주소       + /api/alerts/TX000003/graph?hops=2&lookback_days=7
explanation 주소 + /api/alerts/TX000003/explanation  (POST 후 GET)
analysis 주소    + /api/alerts/TX000003/analysis
```

## 4. 프론트엔드와 팀원에게 주소 전달

프론트엔드 환경변수의 네 값을 실제 배포 주소로 바꿉니다. 아래 `YOUR-...`는 자리표시자이며 배포된 주소가 아닙니다.

```dotenv
VITE_ALERTS_BASE_URL=https://YOUR-ALERTS-SERVICE.onrender.com
VITE_GRAPH_BASE_URL=https://YOUR-GRAPH-SERVICE.onrender.com
VITE_EXPLANATION_BASE_URL=https://YOUR-EXPLANATION-SERVICE.onrender.com
VITE_ANALYSIS_BASE_URL=https://YOUR-ANALYSIS-SERVICE.onrender.com
```

Base URL에는 `/api`를 붙이지 않습니다. 클라이언트가 기존 경로를 추가합니다. Vite 개발 서버는 환경변수 변경 후 재시작하고, 배포된 프론트엔드는 새 설정으로 다시 빌드합니다. 클라이언트 코드는 [프론트엔드 연동 안내](FRONTEND_INTEGRATION.md)를 사용합니다. Python Agent도 네 실제 주소를 각각 설정해서 호출하면 됩니다.

브라우저에서 호출할 프론트엔드의 Origin을 공통 그룹 `fraudgt-mock-shared`의 `CORS_ORIGINS`에 넣습니다. 로컬 React 개발 서버의 기본 허용값은 이미 포함되어 있습니다.

```text
http://localhost:3000,http://localhost:5173,https://실제-프론트엔드-주소
```

프론트엔드 주소에 경로·마지막 `/`를 넣지 않습니다. 네 API 서버 주소가 아니라 **웹 화면이 실행되는 프론트엔드 주소**를 넣습니다. `render.yaml`의 공통 그룹 값을 수정해 커밋하면 다음 Blueprint 동기화에도 설정을 유지할 수 있습니다. Dashboard에서만 변경한 값은 나중에 Blueprint 값으로 덮어써질 수 있습니다.

이 서버는 현재 인증 없는 합성 데이터 Mock입니다. CORS는 브라우저 호출 허용 설정이며 사용자 로그인이나 API 접근 권한 관리 기능이 아닙니다.

팀원에게 네 Base URL, 각 `/docs` 주소, [API 예시](API_EXAMPLES.md)를 전달하면 별도 로컬 서버 없이 사용할 수 있습니다. 이 배포는 백엔드 API이며 프론트엔드 화면 자체를 배포하지는 않습니다.

## 5. 배포 후 전체 점검

네 서비스가 모두 실제 Swagger 화면까지 준비된 다음 로컬에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py `
  --alerts-base-url 'https://YOUR-ALERTS-SERVICE.onrender.com' `
  --graph-base-url 'https://YOUR-GRAPH-SERVICE.onrender.com' `
  --explanation-base-url 'https://YOUR-EXPLANATION-SERVICE.onrender.com' `
  --analysis-base-url 'https://YOUR-ANALYSIS-SERVICE.onrender.com' `
  --timeout 120
```

이 점검은 실제 설명 POST를 한 번 호출하고 결과를 조회합니다. 기본 Origin은 `http://localhost:5173`입니다. 다른 프론트엔드 Origin으로 CORS를 확인하려면 `--origin 'https://실제-프론트엔드-주소'`도 전달합니다.

## Free 플랜에서 달라지는 점

Render Free Web Service는 15분 동안 요청이 없으면 내려가고, 다음 요청으로 다시 시작하는 데 약 1분이 걸릴 수 있습니다. 워크스페이스별 월 750 무료 인스턴스 시간을 여러 서비스가 함께 사용합니다. 네 서비스가 동시에 1시간 실행되면 총 4시간을 소비하므로 4개를 한 달 내내 켜두는 구성은 이 한도에 들어가지 않습니다. [공식 Free 플랜 제한](https://render.com/docs/free)

현재 설명 작업은 프로세스 메모리에 있으므로 재시작·재배포·슬립 후 재기동 시 `not_requested`로 초기화됩니다. 합성 거래와 고정 예측은 Git에 포함된 Fixture에서 다시 적재됩니다. 설명 요청은 다시 POST하면 됩니다. 팀 개발용 Mock으로 먼저 사용할 수 있으며, 계속 켜진 서비스가 필요하면 각 서비스의 유료 Compute Plan과 공유 작업 저장소를 별도로 검토합니다.

## 오류가 날 때 확인할 항목

| 증상 | 확인 |
|---|---|
| `requirements.lock.txt` 또는 `app`을 찾지 못함 | Git 저장소 루트·서비스 Root Directory |
| 포트를 찾지 못함 | Start Command의 `--host 0.0.0.0 --port $PORT` |
| Swagger는 열리지만 프론트에서 CORS 오류 | 모든 서비스가 읽는 `CORS_ORIGINS`에 정확한 프론트엔드 Origin 추가 |
| 그래프 주소에서 목록 API가 404 | API별 서비스 주소를 구분해서 호출 |
| 첫 요청이 오래 걸림 또는 일시적으로 JSON 대신 Render 시작 화면이 나옴 | Free 서비스 재기동을 기다려 실제 Swagger가 열린 뒤 재시도 |
| 설명이 `not_requested`로 바뀜 | 설명 서비스 재시작 여부 확인 후 POST 재요청 |
