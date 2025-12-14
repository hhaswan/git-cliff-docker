# Perbandingan dengan git-cliff Original

## Apa itu git-cliff?

[git-cliff](https://github.com/orhun/git-cliff) adalah tool CLI untuk generate changelog dari commit history berdasarkan [Conventional Commits](https://www.conventionalcommits.org/).

## Perbedaan Utama

| Aspek | git-cliff (Original) | git-cliff-docker (Repo Ini) |
|-------|---------------------|----------------------------|
| **Tipe** | CLI Tool | HTTP API Service |
| **Penggunaan** | Dijalankan langsung di terminal | Diakses via REST API |
| **Instalasi** | `cargo install git-cliff` | `docker compose up -d` |
| **Integrasi CI/CD** | Perlu install di runner | Cukup `curl` ke service |
| **Repository** | Harus clone/checkout lokal | Clone otomatis via API |
| **Konfigurasi** | File `cliff.toml` statis | Dinamis berdasarkan `GITLAB_URL` |
| **Multi-project** | Satu project per eksekusi | Banyak project, satu service |

## Kapan Menggunakan git-cliff Original?

- Generate changelog di local development
- CI/CD dengan Docker runner (bisa install git-cliff di image)
- Project yang sudah punya `cliff.toml` custom
- Butuh fitur advanced git-cliff

## Kapan Menggunakan Repo Ini?

- GitLab self-hosted dengan **Shell Runner**
- Tidak ingin install dependencies di setiap runner
- Butuh **centralized service** untuk banyak project
- Ingin generate changelog via **HTTP API**
- Integrasi dengan sistem lain yang bisa call REST API

## Arsitektur

**git-cliff Original:**
```
Developer/CI → install git-cliff → run di repo lokal → output changelog
```

**git-cliff-docker (Repo Ini):**
```
GitLab CI/CD → curl HTTP API → Service clone repo → generate changelog → return response
```

## Fitur yang Sama

- Conventional Commits parsing
- Customizable template
- Semantic versioning bump
- Multiple output format (markdown, JSON)
- Tag range filtering

## Fitur Tambahan di Repo Ini

- REST API endpoints
- Auto-clone repository dari GitLab
- Dynamic config berdasarkan GITLAB_URL
- Docker containerized deployment
- GitLab CI/CD templates siap pakai
- Health check endpoint

## Links

- **git-cliff Original:** https://github.com/orhun/git-cliff
- **git-cliff Documentation:** https://git-cliff.org/
