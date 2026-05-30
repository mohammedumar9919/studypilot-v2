# Docker setup — studypilot-v2 (Windows)

**Generated:** 2026-05-23  
**Machine:** Windows 10 Pro (build 26100)  
**Project:** `C:\Projects\studypilot-v2`

## Summary

| Item | Status |
|------|--------|
| Docker / Docker Desktop | **Not installed** (install was started but not completed) |
| `docker.exe` path | **None found** |
| Postgres on `localhost:5433` | **Not running** (connection refused) |
| `pip install -e ".[dev]"` | **Success** (`apps\api\.venv`) |
| Alembic `upgrade head` | **Not completed** (blocked: no database) |
| PPL ingest (`scripts\ingest_ppl.ps1`) | **Skipped** (requires migrations + Postgres) |

## Docker search results

### PATH and command resolution

- `where.exe docker` — no matches (exit code 1)
- `Get-Command docker` — not found
- `%PATH%` — no Docker-related entries

### Common install locations (all missing)

| Path | Result |
|------|--------|
| `C:\Program Files\Docker\Docker\resources\bin\docker.exe` | Not present |
| `C:\Program Files\Docker\Docker\Docker Desktop.exe` | Not present |
| `%LOCALAPPDATA%\Programs\Docker\Docker\resources\bin\docker.exe` | Not present |
| `C:\Program Files (x86)\Docker` | Not present |

### Registry

- `HKLM\...\Uninstall\*` — no DisplayName matching `*Docker*`
- `HKLM\SOFTWARE\Docker Inc.` — not present
- `HKCU\SOFTWARE\Docker Inc.` — not present

### Package managers

- `winget list Docker.DockerDesktop` — **No installed package found**
- Chocolatey — no docker-desktop package listed

### WSL

- `wsl --status` — **WSL is not installed** (`wsl.exe --install` required for Docker Desktop backend on Windows)

### Filesystem scans

- Recursive search under `C:\Program Files` (depth 5) for `docker.exe` — none
- Recursive search under `C:\Users\Owner` (depth 8) for `docker.exe` — none
- Recursive search under `C:\` (depth 6) for `docker.exe` — none
- Search for `Docker Desktop.exe` under Program Files (depth 4) — none

### Partial / failed install evidence

`%LOCALAPDATA%\Docker\` exists with installer logs only (no binaries):

- `install-log.txt`, `install-log.0.txt`, `install-log.1.txt`

Docker Desktop **4.71.0 (225177)** installer was launched from Temp but:

1. Log: `[Installer][I] No installation found`
2. Relaunched for UAC elevation (admin required)
3. `install-log.1.txt`: **`The operation was canceled by the user`** (UAC prompt declined or canceled)

**Conclusion:** Docker Desktop is **not** installed on this PC. There is no absolute path to `docker.exe` or `Docker Desktop.exe`.

## Intended workflow (after Docker is installed)

From repo root:

```powershell
cd C:\Projects\studypilot-v2
docker compose up -d
```

If Docker is installed but not on PATH, use the full path (typical after a successful install):

```powershell
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose up -d
```

### Wait for Postgres (host port **5433**)

Compose maps `5433:5432`. Example health wait:

```powershell
$deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $deadline) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $c.Connect("127.0.0.1", 5433)
    $c.Close()
    Write-Host "Postgres port 5433 is open"
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}
```

Optional: `docker compose ps` and container logs once `docker` is available.

### Migrations

```powershell
cd C:\Projects\studypilot-v2\apps\api
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
python -m alembic upgrade head
```

### PPL ingest (both PDFs)

```powershell
cd C:\Projects\studypilot-v2
.\scripts\ingest_ppl.ps1
```

Fixtures verified present:

- `eval\fixtures\ppl\PPL notes.pdf`
- `eval\fixtures\ppl\PPL previous papers.pdf`

## Commands run on this session (2026-05-23)

1. Docker discovery — see search section above; **no `docker compose up -d`** (no binary).
2. Port check — `127.0.0.1:5433` **actively refused**.
3. `cd C:\Projects\studypilot-v2\apps\api` — used existing `.venv`, `pip install -e ".[dev]"` **succeeded**.
4. `python -m alembic upgrade head` with `DATABASE_URL` above — **hung** with no DB (process terminated after ~2 min).

## Install Docker Desktop (user action required)

1. Download: https://docs.docker.com/desktop/setup/install/windows-install/
2. Run **Docker Desktop Installer** as Administrator (accept UAC).
3. Enable/use WSL 2 when prompted, or install WSL first:
   ```powershell
   wsl --install
   ```
   Reboot if required, then finish Docker Desktop setup.
4. Alternative via winget (elevated terminal):
   ```powershell
   winget install Docker.DockerDesktop
   ```
5. Start **Docker Desktop** from the Start menu; wait until the engine is running.
6. Re-run the workflow sections above.

## Blockers

1. **Complete Docker Desktop installation** (admin/UAC; prior attempt canceled).
2. **WSL 2** may be required — not currently installed.
3. Until Postgres is up on **5433**, migrations and ingest cannot succeed.

## Install attempt (2026-05-24, automated agent)

### Environment checks

| Check | Result |
|-------|--------|
| Shell elevated (
et session) | **No** — Access is denied (error 5) |
| whoami /groups Administrators | Present as **deny-only** alias (not an elevated token) |
| winget --version | v1.28.240 |
| where.exe docker | Not found |
| wsl --status | **WSL not installed** — run `wsl --install` then reboot before Docker Desktop can use WSL 2 backend |
| winget list Docker.DockerDesktop | No installed package |

### Attempt 1: winget (non-elevated)

```powershell
winget install Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
```

- Package resolved: **Docker Desktop 4.73.0 (226246)**
- Installer downloaded and hash verified (~617 MB)
- Installer exited with code **4294967291** (elevation/UAC not completed)
- Log: `%LOCALAPPDATA%\Docker\install-log.txt` — `Not run as admin, relaunching with UAC prompt`

### Attempt 2: official installer download + RunAs

- Downloaded: `C:\Users\Owner\AppData\Local\Temp\DockerDesktopInstaller.exe` (**655,622,064** bytes, complete)
- Source: `https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe`
- `Start-Process -Verb RunAs` on that file: **process start reported success**; no binaries under `C:\Program Files\Docker\` afterward (UAC likely not approved in unattended session)

### Attempt 3: elevated winget via RunAs

```powershell
Start-Process winget -ArgumentList 'install','Docker.DockerDesktop','--accept-package-agreements','--accept-source-agreements' -Verb RunAs
```

- Parent reported **RunAs started** (~268 s); **Docker still not registered** in winget afterward

### Post-attempt verification

| Item | Result |
|------|--------|
| `C:\Program Files\Docker\Docker\Docker Desktop.exe` | **Missing** |
| `C:\Program Files\Docker\Docker\resources\bin\docker.exe` | **Missing** |
| `docker compose up -d` | **Not run** (no docker) |
| `alembic upgrade head` | **Not run** (no Postgres) |

### User action required (one elevated PowerShell window)

**Automated agents cannot click UAC.** Run **PowerShell as Administrator** and execute **in order**:

1. **Install WSL 2** (required on this machine):

```powershell
wsl --install
```

Reboot when prompted, complete Ubuntu/WSL first-run if asked.

2. **Install Docker Desktop** (either command):

```powershell
winget install Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
```

Or, if the cached installer is still present:

```powershell
Start-Process -FilePath "C:\Users\Owner\AppData\Local\Temp\DockerDesktopInstaller.exe" -Wait
```

Click **Yes** on the UAC prompt. Finish the Docker Desktop wizard (WSL 2 backend).

3. **Start Docker Desktop** from the Start menu; wait until the engine is **Running**.

4. **From repo root**:

```powershell
cd C:\Projects\studypilot-v2
docker compose up -d
cd apps\api
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
python -m alembic upgrade head
```

Expected `docker.exe` after success: `C:\Program Files\Docker\Docker\resources\bin\docker.exe`


## Elevated PowerShell attempt (2026-05-24, agent sub-session)

Automated pass executed from a **non-elevated** Cursor agent shell. Goal: determine whether Docker Desktop can be installed **without an interactive UAC click**.

### Step 1 — Elevation detection

| Check | Result |
|-------|--------|
| `net session` | **Failed** — System error 5 (Access is denied) → **not elevated** |
| `[WindowsPrincipal]::IsInRole(Administrator)` | **False** |
| `whoami /groups` | `BUILTIN\Administrators` and `S-1-5-114` listed as **Group used for deny only** (split token, admin rights not active) |

### Step 2 — `Start-Process -Verb RunAs` + winget (silent)

```powershell
Start-Process winget -ArgumentList 'install','--id','Docker.DockerDesktop','--accept-package-agreements','--accept-source-agreements','--silent' -Verb RunAs -Wait
```

- **Outcome:** Job did **not** complete within 8s → **blocked waiting for UAC** (no unattended completion).
- **Post-check:** Docker still not installed.

### Step 3 — Cached installer (`%TEMP%\DockerDesktopInstaller.exe`)

| Item | Value |
|------|-------|
| Path | `C:\Users\Owner\AppData\Local\Temp\DockerDesktopInstaller.exe` |
| Size | **655,622,064** bytes (present) |
| `docker.exe` under Program Files | **Still missing** after attempts |

Silent flags (from Docker installer log + docs): the official CLI is:

```text
"Docker Desktop Installer.exe" install --quiet
```

Optional internal form (seen in `%LOCALAPPDATA%\Docker\install-log.txt`):

```text
install -package <path>\DockerDesktop.d4w --quiet
```

**RunAs attempt:**

```powershell
Start-Process -FilePath "$env:TEMP\DockerDesktopInstaller.exe" -ArgumentList 'install','--quiet','--accept-license' -Verb RunAs -Wait
```

- **Outcome:** Parent `Start-Process` returned quickly; elevated child likely **spawned UAC** — no files under `C:\Program Files\Docker\` afterward.
- **Non-elevated winget** (same session) re-ran installer with `--quiet`; log line: **`Not run as admin, relaunching with UAC prompt`**.

### Step 4 — Docker Desktop silent install (research)

- **Winget:** `Docker.DockerDesktop` → Installer type **exe**, silent via `--silent` on winget; installer still requires **admin** for actual setup.
- **EXE:** Documented silent mode is **`install --quiet`** (accept license is implied in quiet enterprise flows; GUI wizard skipped only **after** elevation succeeds).
- **Conclusion:** Silent flags reduce UI **after** admin token is granted; they do **not** bypass UAC.

### Step 5 — `wsl --install` via RunAs

```powershell
Start-Process wsl -ArgumentList '--install','--no-distribution' -Verb RunAs -Wait
```

- **Outcome:** Did **not** complete within 8s → **blocked on UAC** (same as Docker).
- **`wsl --status`:** WSL optional component **not fully enabled** on this machine (Docker Desktop WSL2 backend still needs admin + likely reboot).

### Step 6 — Other non-interactive paths

| Path | Result |
|------|--------|
| `winget install ...` (current shell, no RunAs) | Exit **4294967291** — elevation required |
| `choco install docker-desktop -y` | **Failed (exit 1)** — could not obtain Chocolatey lock file under `C:\ProgramData\chocolatey\lib\` (permission/elevation; process was stopped after ~80s) |

### Post-attempt verification

| Check | Result |
|-------|--------|
| `Test-Path 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'` | **False** |
| `winget list --id Docker.DockerDesktop` | **No installed package found** |
| `docker --version` | **Command not found** |

### Agent verdict

| Question | Answer |
|----------|--------|
| Can the agent finish Docker Desktop install **without the user clicking UAC**? | **No** |
| Why? | Every viable path (`winget`, official `.exe install --quiet`, `wsl --install`, Chocolatey) requires an **elevated administrator token**. `-Verb RunAs` only **displays** the UAC dialog; it cannot be auto-approved in this environment. |

### User: one elevated command block

Open **PowerShell as Administrator** (Start → PowerShell → right-click → **Run as administrator**), approve UAC once, then paste:

```powershell
wsl --install --no-distribution; winget install --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements; if ($LASTEXITCODE -ne 0 -and (Test-Path "$env:TEMP\DockerDesktopInstaller.exe")) { Start-Process -FilePath "$env:TEMP\DockerDesktopInstaller.exe" -ArgumentList 'install','--quiet' -Wait }
```

Reboot if `wsl --install` requests it, start **Docker Desktop** from the Start menu, then verify:

```powershell
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" --version
```

