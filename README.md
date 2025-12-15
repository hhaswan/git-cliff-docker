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
| `GITLAB_TOKEN` | **Personal Access Token** (PAT) dengan scope `read_repository`, `write_repository`, `api` | Yes | Yes |

**Cara membuat Personal Access Token (PAT):**
1. Buka GitLab → Klik avatar di pojok kanan atas → **Preferences**
2. Di sidebar kiri, pilih **Access Tokens**
3. Atau langsung akses: `https://<gitlab-url>/-/user_settings/personal_access_tokens`
4. Isi form:
   - **Token name**: `changelog-service` (atau nama lain)
   - **Expiration date**: Set sesuai kebutuhan
   - **Scopes**: Centang `api`, `read_repository`, `write_repository`
5. Klik **Create personal access token**
6. **Copy token** yang muncul (hanya ditampilkan sekali!)

> **Penting tentang GITLAB_TOKEN:**
> - Gunakan **Personal Access Token (PAT)**, bukan Project Access Token
> - Project Access Token tidak memiliki akses yang cukup untuk operasi git push dan create release
> - PAT harus dibuat oleh user yang memiliki akses ke project

> **Penting tentang Protected Variables:**
> - Jika variable di-set sebagai **Protected = Yes**, maka variable hanya tersedia untuk protected branches dan **protected tags**
> - Pastikan tag yang dibuat juga ter-protect, atau set variable sebagai **Protected = No**
> - Untuk protect semua tags: **Settings > Repository > Protected tags** → tambahkan pattern `*` atau `v*`

### 4. Tambahkan ke .gitlab-ci.yml

Copy snippet dari `examples/gitlab-ci-snippet.yml` ke `.gitlab-ci.yml` project Anda:

```yaml
stages:
    - build
    - deploy
    - changelog  # Tambahkan stage ini

# ... existing jobs ...

# Generate release notes dan create GitLab Release saat ada tag
changelog:release:
    stage: changelog
    tags: [builder]
    allow_failure: true
    rules:
        - if: '$CI_COMMIT_TAG'
          when: always
    script:
        # Generate release notes untuk tag ini
        - |
            curl -s -X POST "${CHANGELOG_SERVICE_URL}/api/v1/release-notes" \
                -H "Content-Type: application/json" \
                -H "X-API-Token: ${CHANGELOG_API_TOKEN}" \
                -d "{
                    \"project_path\": \"${CI_PROJECT_PATH}\",
                    \"gitlab_token\": \"${GITLAB_TOKEN}\",
                    \"tag\": \"${CI_COMMIT_TAG}\"
                }" > RELEASE_NOTES.md
        - echo "=== Release Notes for ${CI_COMMIT_TAG} ==="
        - cat RELEASE_NOTES.md
        # Create GitLab Release dengan release notes
        - |
            RELEASE_NOTES=$(cat RELEASE_NOTES.md | sed 's/"/\\"/g' | awk '{printf "%s\\n", $0}')
            curl -s -X POST "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/releases" \
                -H "Content-Type: application/json" \
                -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
                -d "{
                    \"tag_name\": \"${CI_COMMIT_TAG}\",
                    \"name\": \"Release ${CI_COMMIT_TAG}\",
                    \"description\": \"${RELEASE_NOTES}\"
                }"
        - echo "GitLab Release created for ${CI_COMMIT_TAG}"

# Generate dan commit CHANGELOG.md ke repo (otomatis saat tag)
changelog:update:
    stage: changelog
    tags: [builder]
    allow_failure: true
    rules:
        - if: '$CI_COMMIT_TAG'
        - if: '$CI_COMMIT_BRANCH == "develop"'
          when: manual
    before_script:
        - git config --global user.email "gitlab-ci@${CI_SERVER_HOST}"
        - git config --global user.name "GitLab CI"
    script:
        # Generate full changelog dari service
        - |
            curl -s -X POST "${CHANGELOG_SERVICE_URL}/api/v1/changelog" \
                -H "Content-Type: application/json" \
                -H "X-API-Token: ${CHANGELOG_API_TOKEN}" \
                -d "{
                    \"project_path\": \"${CI_PROJECT_PATH}\",
                    \"gitlab_token\": \"${GITLAB_TOKEN}\"
                }" > CHANGELOG.md
        - echo "=== Full Changelog Generated ==="
        - cat CHANGELOG.md
        # Clone repo dan push CHANGELOG.md
        - git clone "https://oauth2:${GITLAB_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git" repo
        - cp CHANGELOG.md repo/
        - cd repo
        - git add CHANGELOG.md
        - |
            if git diff --cached --quiet; then
                echo "No changes to CHANGELOG.md"
            else
                TAG_INFO="${CI_COMMIT_TAG:-${CI_COMMIT_SHORT_SHA}}"
                git commit -m "docs: update CHANGELOG.md for ${TAG_INFO} [skip ci]"
                git push origin HEAD:main
                echo "CHANGELOG.md updated and pushed to main"
            fi
```

> **Catatan untuk Shell Runner:**
> - `before_script` dengan `git config --global` diperlukan untuk mengatur identitas git saat commit
> - Jika tidak di-set, git commit akan gagal karena tidak ada user.email dan user.name

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

### Contoh Output

**CHANGELOG.md (Full Changelog):**
```markdown
# Changelog

Semua perubahan penting pada proyek ini akan didokumentasikan di file ini.

## [1.2.0] - 2025-12-16

### 🚀 Features
- **auth:** Add OAuth2 login support ([a1b2c3d](https://gitlab.example.com/mygroup/myproject/-/commit/a1b2c3d))
- **api:** Implement rate limiting ([e4f5g6h](https://gitlab.example.com/mygroup/myproject/-/commit/e4f5g6h))

### 🐛 Bug Fixes
- **login:** Fix session timeout issue ([i7j8k9l](https://gitlab.example.com/mygroup/myproject/-/commit/i7j8k9l))
- Resolve database connection leak ([m0n1o2p](https://gitlab.example.com/mygroup/myproject/-/commit/m0n1o2p))

### 📚 Documentation
- Update API documentation ([q3r4s5t](https://gitlab.example.com/mygroup/myproject/-/commit/q3r4s5t))

### ⚙️ Miscellaneous
- Update dependencies ([u6v7w8x](https://gitlab.example.com/mygroup/myproject/-/commit/u6v7w8x))

## [1.1.0] - 2025-12-01

### 🚀 Features
- Add user profile page ([y9z0a1b](https://gitlab.example.com/mygroup/myproject/-/commit/y9z0a1b))

### 🐛 Bug Fixes
- Fix pagination issue ([c2d3e4f](https://gitlab.example.com/mygroup/myproject/-/commit/c2d3e4f))
```

**Release Notes (untuk tag tertentu):**
```markdown
## [1.2.0] - 2025-12-16

### 🚀 Features
- **auth:** Add OAuth2 login support ([a1b2c3d](https://gitlab.example.com/mygroup/myproject/-/commit/a1b2c3d))
- **api:** Implement rate limiting ([e4f5g6h](https://gitlab.example.com/mygroup/myproject/-/commit/e4f5g6h))

### 🐛 Bug Fixes
- **login:** Fix session timeout issue ([i7j8k9l](https://gitlab.example.com/mygroup/myproject/-/commit/i7j8k9l))
- Resolve database connection leak ([m0n1o2p](https://gitlab.example.com/mygroup/myproject/-/commit/m0n1o2p))

### 📚 Documentation
- Update API documentation ([q3r4s5t](https://gitlab.example.com/mygroup/myproject/-/commit/q3r4s5t))
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

| Prefix | Kategori | Deskripsi | Contoh |
|--------|----------|-----------|--------|
| `feat:` | 🚀 Features | Fitur baru | `feat: add user authentication` |
| `fix:` | 🐛 Bug Fixes | Perbaikan bug | `fix: resolve login issue` |
| `docs:` | 📚 Documentation | Perubahan dokumentasi saja | `docs: update README` |
| `perf:` | ⚡ Performance | Peningkatan performa | `perf: optimize database query` |
| `refactor:` | ♻️ Refactoring | Refactoring tanpa mengubah fitur | `refactor: restructure modules` |
| `style:` | 🎨 Styling | Formatting, whitespace, dll | `style: fix indentation` |
| `test:` | 🧪 Testing | Menambah atau memperbaiki tests | `test: add unit tests` |
| `build:` | 🔧 DevOps & Infrastructure | Build system, Docker, dependencies | `build: upgrade base docker image` |
| `ci:` | 🔧 DevOps & Infrastructure | CI/CD pipeline configuration | `ci: add deploy stage to pipeline` |
| `chore:` | ⚙️ Miscellaneous | Maintenance tasks lainnya | `chore: cleanup unused files` |
| `revert:` | ⏪ Revert | Revert commit sebelumnya | `revert: revert commit abc123` |

**Contoh dengan scope:**
```bash
feat(auth): add OAuth2 login
fix(api): resolve rate limiting bug
build(docker): upgrade python to 3.12
ci(gitlab): add changelog automation
```

## Troubleshooting

### Service tidak bisa clone repository
- Pastikan `GITLAB_TOKEN` memiliki scope `read_repository`
- Pastikan URL GitLab benar di `.env`

### Error 401 Unauthorized
- Pastikan `X-API-Token` header sesuai dengan `CHANGELOG_API_TOKEN` di `.env`

### Changelog kosong
- Pastikan project memiliki tags
- Pastikan commit message mengikuti format Conventional Commits

### Error "HTTP Basic: Access denied" saat git clone/push
- Pastikan menggunakan **Personal Access Token (PAT)**, bukan Project Access Token
- Pastikan token memiliki scope `write_repository` untuk operasi push
- Cek apakah token sudah expired

### CI/CD Variables tidak terbaca (Unauthorized pada push ke-2, dst)
- Jika variable di-set sebagai **Protected**, pastikan tag juga ter-protect
- Solusi 1: Set variable sebagai **Protected = No**
- Solusi 2: Protect semua tags di **Settings > Repository > Protected tags** dengan pattern `*`

### Git commit gagal: "Please tell me who you are"
- Tambahkan `before_script` untuk set git config:
```yaml
before_script:
    - git config --global user.email "gitlab-ci@${CI_SERVER_HOST}"
    - git config --global user.name "GitLab CI"
```

## License

MIT