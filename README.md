# Git-Cliff Changelog Service

Self-hosted changelog & release notes service untuk GitLab (self-managed), dibangun menggunakan [git-cliff](https://github.com/orhun/git-cliff).

> **Reference:** This project is built on top of [git-cliff](https://github.com/orhun/git-cliff) - a highly customizable changelog generator.
>
> Lihat [COMPARISON.md](COMPARISON.md) untuk perbedaan dengan git-cliff original.

## Arsitektur

```
┌─────────────────┐         ┌──────────────────────────┐
│   GitLab CI/CD  │   HTTP  │   Changelog Service      │
│  (Shell Runner) │ ──────► │   (Container di Server)  │
│                 │   API   │                          │
└─────────────────┘         └──────────────────────────┘
       curl                    - Generate changelog
                               - Return markdown/JSON
```

## Quick Start

### 1. Build & Deploy

```bash
# Clone repository
git clone <repo-url> changelog-service
cd changelog-service

# Copy dan edit environment variables
cp .env.example .env
nano .env

# Build dan jalankan
docker compose up -d --build

# Cek status
docker compose ps
docker compose logs -f
```

**Default:** Service berjalan di port `8080`

**Perintah Docker:**
```bash
# Stop service
docker compose down

# Restart service
docker compose restart

# Rebuild setelah update
docker compose up -d --build --force-recreate

# Lihat logs
docker compose logs -f changelog-service
```

### 2. Konfigurasi Environment Variables

Edit file `.env`:

```env
TZ=Asia/Jakarta                          # Timezone
GITLAB_URL=https://gitlab.example.com    # URL GitLab self-hosted
CHANGELOG_API_TOKEN=your-secure-token    # Token untuk API
DEBUG=false                              # Debug mode
PORT=8080                                # Port host (default: 8080)
```

**Generate CHANGELOG_API_TOKEN:**
```bash
# Linux/Mac
openssl rand -hex 32

# Atau
head -c 32 /dev/urandom | base64 | tr -d '=/+'

# Windows PowerShell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Max 256 }) -as [byte[]])
```

Token ini digunakan untuk autentikasi request ke API service. Simpan token yang sama di:
1. File `.env` pada server changelog service
2. GitLab CI/CD Variables pada setiap project

### 3. Setup GitLab CI/CD Variables

Di GitLab project, tambahkan variabel di **Settings > CI/CD > Variables**:

| Variable | Value | Protected | Masked |
|----------|-------|-----------|--------|
| `CHANGELOG_SERVICE_URL` | `http://<server-ip>:8080` | No | No |
| `CHANGELOG_API_TOKEN` | Token yang sama dengan `.env` | Yes | Yes |
| `GITLAB_TOKEN` | Personal Access Token dengan scope `read_repository`, `api` | Yes | Yes |

### 4. Tambahkan ke .gitlab-ci.yml

Copy snippet dari `examples/gitlab-ci-snippet.yml` ke `.gitlab-ci.yml` project Anda:

```yaml
stages:
    - build
    - deploy
    - changelog  # Tambahkan stage ini

# ... existing jobs ...

# Generate release notes saat ada tag
changelog:release_notes:
    stage: changelog
    tags: [builder]
    allow_failure: true
    rules:
        - if: '$CI_COMMIT_TAG'
    script:
        - |
            curl -s -X POST "${CHANGELOG_SERVICE_URL}/api/v1/release-notes" \
                -H "Content-Type: application/json" \
                -H "X-API-Token: ${CHANGELOG_API_TOKEN}" \
                -d "{
                    \"project_path\": \"${CI_PROJECT_PATH}\",
                    \"gitlab_token\": \"${GITLAB_TOKEN}\",
                    \"tag\": \"${CI_COMMIT_TAG}\"
                }" > RELEASE_NOTES.md
            cat RELEASE_NOTES.md
    artifacts:
        paths:
            - RELEASE_NOTES.md
```

## API Endpoints

| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/health` | GET | Health check |
| `/api/v1/changelog` | POST | Generate full changelog |
| `/api/v1/release-notes` | POST | Generate release notes untuk tag tertentu |
| `/api/v1/bump-version` | POST | Dapatkan versi berikutnya |

**Test Health Check:**
```bash
curl http://localhost:8080/health
```

### Contoh Request

**Generate Full Changelog:**
```bash
curl -X POST http://localhost:8080/api/v1/changelog \
  -H "Content-Type: application/json" \
  -H "X-API-Token: your-token" \
  -d '{
    "project_path": "devops/my-project",
    "gitlab_token": "glpat-xxxx"
  }'
```

**Generate Release Notes:**
```bash
curl -X POST http://localhost:8080/api/v1/release-notes \
  -H "Content-Type: application/json" \
  -H "X-API-Token: your-token" \
  -d '{
    "project_path": "devops/my-project",
    "gitlab_token": "glpat-xxxx",
    "tag": "v1.2.0"
  }'
```

**Get Bumped Version:**
```bash
curl -X POST http://localhost:8080/api/v1/bump-version \
  -H "Content-Type: application/json" \
  -H "X-API-Token: your-token" \
  -d '{
    "project_path": "devops/my-project",
    "gitlab_token": "glpat-xxxx"
  }'
```

## Struktur Project

```
git-cliff-docker/
├── app/
│   └── main.py              # Flask API server
├── config/
│   └── cliff.toml           # Default git-cliff config
├── examples/
│   ├── gitlab-ci-changelog.yml  # Full CI template
│   └── gitlab-ci-snippet.yml    # Snippet untuk existing CI
├── scripts/
│   └── changelog.sh         # Helper script
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Konfigurasi Changelog (cliff.toml)

File `config/cliff.toml` mengatur format changelog. Secara default menggunakan:
- Conventional Commits (feat, fix, docs, etc.)
- Emoji untuk kategori
- Link ke GitLab issues dan merge requests

Anda bisa mengedit file ini atau mengirim custom config via API.

## Conventional Commits

Service ini menggunakan [Conventional Commits](https://www.conventionalcommits.org/) untuk mengkategorikan perubahan:

| Prefix | Kategori | Contoh |
|--------|----------|--------|
| `feat:` | Features | `feat: add user authentication` |
| `fix:` | Bug Fixes | `fix: resolve login issue` |
| `docs:` | Documentation | `docs: update README` |
| `perf:` | Performance | `perf: optimize query` |
| `refactor:` | Refactoring | `refactor: restructure modules` |
| `test:` | Testing | `test: add unit tests` |
| `chore:` | Miscellaneous | `chore: update dependencies` |

## Troubleshooting

### Service tidak bisa clone repository
- Pastikan `GITLAB_TOKEN` memiliki scope `read_repository`
- Pastikan URL GitLab benar di `.env`

### Error 401 Unauthorized
- Pastikan `X-API-Token` header sesuai dengan `CHANGELOG_API_TOKEN` di `.env`

### Changelog kosong
- Pastikan project memiliki tags
- Pastikan commit message mengikuti format Conventional Commits

## License

MIT
