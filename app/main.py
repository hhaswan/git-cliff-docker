#!/usr/bin/env python3
"""
Git-Cliff Changelog Service API
================================
HTTP API service untuk generate changelog menggunakan git-cliff.
Dirancang untuk integrasi dengan GitLab CI/CD (Shell Runner).
"""

import os
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Optional
from flask import Flask, request, jsonify, Response
from functools import wraps

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Konfigurasi
API_TOKEN = os.environ.get('CHANGELOG_API_TOKEN', 'changeme')
GITLAB_URL = os.environ.get('GITLAB_URL', 'https://gitlab.example.com')
WORK_DIR = '/tmp/changelog-work'


def get_dynamic_config(gitlab_url: str, project_path: str) -> str:
    """
    Generate konfigurasi cliff.toml secara dinamis berdasarkan gitlab_url dan project_path.
    Link ke issues, merge requests, dan commits akan otomatis sesuai dengan URL GitLab.
    """
    config = f'''# ============================================
# Git-Cliff Configuration (Auto-Generated)
# ============================================
# GitLab URL: {gitlab_url}
# Project: {project_path}

[changelog]
header = """
# Changelog

Semua perubahan penting pada proyek ini akan didokumentasikan di file ini.

"""

body = """
{{% if version -%}}
## [{{{{ version | trim_start_matches(pat="v") }}}}] - {{{{ timestamp | date(format="%Y-%m-%d") }}}}
{{% else -%}}
## [Unreleased]
{{% endif -%}}

{{% for group, commits in commits | group_by(attribute="group") %}}
### {{{{ group | striptags | trim | upper_first }}}}
{{% for commit in commits %}}
- {{% if commit.scope %}}**{{{{ commit.scope }}}}:** {{% endif %}}{{{{ commit.message | upper_first }}}}\\
{{% if commit.id %}} ([{{{{ commit.id | truncate(length=7, end="") }}}}]({gitlab_url}/{project_path}/-/commit/{{{{ commit.id }}}})){{% endif %}}
{{% endfor %}}
{{% endfor %}}
"""

footer = ""
trim = true

postprocessors = [
    {{ pattern = '\\n{{3,}}', replace = "\\n\\n" }},
]

[git]
conventional_commits = true
filter_unconventional = false
split_commits = false
protect_breaking_commits = false

commit_parsers = [
    {{ message = "^feat", group = "🚀 Features" }},
    {{ message = "^fix", group = "🐛 Bug Fixes" }},
    {{ message = "^doc", group = "📚 Documentation" }},
    {{ message = "^perf", group = "⚡ Performance" }},
    {{ message = "^refactor", group = "♻️ Refactoring" }},
    {{ message = "^style", group = "🎨 Styling" }},
    {{ message = "^test", group = "🧪 Testing" }},
    {{ message = "^build|^ci", group = "🔧 DevOps & Infrastructure" }},
    {{ message = "^chore\\\\(release\\\\)", skip = true }},
    {{ message = "^chore\\\\(deps\\\\)", group = "📦 Dependencies" }},
    {{ message = "^chore\\\\(pr\\\\)", skip = true }},
    {{ message = "^chore\\\\(pull\\\\)", skip = true }},
    {{ message = "^chore", group = "⚙️ Miscellaneous" }},
    {{ body = ".*security", group = "🔐 Security" }},
    {{ message = "^revert", group = "⏪ Revert" }},
    {{ message = ".*", group = "📝 Other Changes" }},
]

commit_preprocessors = [
    {{ pattern = '\\((\\w+\\s)?#([0-9]+)\\)', replace = "" }},
]

link_parsers = [
    {{ pattern = "#(\\\\d+)", href = "{gitlab_url}/{project_path}/-/issues/$1" }},
    {{ pattern = "!(\\\\d+)", href = "{gitlab_url}/{project_path}/-/merge_requests/$1" }},
]

tag_pattern = "v?[0-9].*"
sort_commits = "newest"

[bump]
features_always_bump_minor = true
breaking_always_bump_major = true
initial_tag = "0.1.0"
'''
    return config


def require_auth(f):
    """Decorator untuk autentikasi API token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-API-Token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        if token != API_TOKEN:
            logger.warning(f"Unauthorized access attempt from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized', 'message': 'Invalid or missing API token'}), 401
        return f(*args, **kwargs)
    return decorated


def clone_repository(gitlab_url: str, project_path: str, token: str, work_dir: str) -> str:
    """Clone repository dari GitLab."""
    repo_url = f"{gitlab_url.rstrip('/')}/{project_path}.git"

    # Inject token ke URL untuk autentikasi
    if token:
        # Format: https://oauth2:TOKEN@gitlab.example.com/group/project.git
        if repo_url.startswith('https://'):
            repo_url = repo_url.replace('https://', f'https://oauth2:{token}@')
        elif repo_url.startswith('http://'):
            repo_url = repo_url.replace('http://', f'http://oauth2:{token}@')

    repo_dir = os.path.join(work_dir, 'repo')

    logger.info(f"Cloning repository: {project_path}")

    # Clone dengan depth untuk performa (tapi perlu semua tags)
    result = subprocess.run(
        ['git', 'clone', '--bare', repo_url, repo_dir],
        capture_output=True,
        text=True,
        timeout=300
    )

    if result.returncode != 0:
        raise Exception(f"Failed to clone repository: {result.stderr}")

    return repo_dir


def generate_changelog(
    repo_path: str,
    config_path: Optional[str] = None,
    tag_range: Optional[str] = None,
    unreleased: bool = False,
    latest: bool = False,
    output_format: str = 'markdown',
    extra_args: Optional[list] = None
) -> dict:
    """Generate changelog menggunakan git-cliff."""

    cmd = ['git-cliff', '--repository', repo_path]

    # Konfigurasi
    if config_path and os.path.exists(config_path):
        cmd.extend(['--config', config_path])

    # Options
    if unreleased:
        cmd.append('--unreleased')

    if latest:
        cmd.append('--latest')

    if tag_range:
        cmd.append(tag_range)

    # Output sebagai JSON context jika diminta
    if output_format == 'json':
        cmd.append('--context')

    # Extra arguments
    if extra_args:
        cmd.extend(extra_args)

    logger.info(f"Running command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120
    )

    if result.returncode != 0:
        raise Exception(f"git-cliff failed: {result.stderr}")

    return {
        'changelog': result.stdout,
        'format': output_format
    }


def get_bumped_version(repo_path: str, config_path: Optional[str] = None) -> str:
    """Dapatkan versi bump berikutnya."""
    cmd = ['git-cliff', '--repository', repo_path, '--bumped-version']

    if config_path and os.path.exists(config_path):
        cmd.extend(['--config', config_path])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        raise Exception(f"Failed to get bumped version: {result.stderr}")

    return result.stdout.strip()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'changelog-service', 'gitlab_url': GITLAB_URL})


@app.route('/api/v1/changelog', methods=['POST'])
@require_auth
def create_changelog():
    """
    Generate changelog untuk repository GitLab.

    Request body (JSON):
    {
        "project_path": "group/project",       # Required: GitLab project path
        "gitlab_token": "glpat-xxx",           # Required: GitLab access token
        "tag_range": "v1.0.0..v2.0.0",         # Optional: Tag range
        "unreleased": false,                    # Optional: Include unreleased
        "latest": false,                        # Optional: Only latest tag
        "output_format": "markdown",            # Optional: markdown atau json
        "config": "..."                         # Optional: Custom cliff.toml content
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Bad Request', 'message': 'JSON body required'}), 400

        project_path = data.get('project_path')
        gitlab_token = data.get('gitlab_token')

        if not project_path:
            return jsonify({'error': 'Bad Request', 'message': 'project_path is required'}), 400

        if not gitlab_token:
            return jsonify({'error': 'Bad Request', 'message': 'gitlab_token is required'}), 400

        # Buat temporary work directory
        work_dir = tempfile.mkdtemp(prefix='changelog-', dir=WORK_DIR)

        try:
            # Clone repository
            repo_path = clone_repository(GITLAB_URL, project_path, gitlab_token, work_dir)

            # Generate config: gunakan custom jika ada, atau generate dinamis
            config_path = os.path.join(work_dir, 'cliff.toml')
            if data.get('config'):
                with open(config_path, 'w') as f:
                    f.write(data['config'])
            else:
                # Generate config dinamis berdasarkan GITLAB_URL dan project_path
                dynamic_config = get_dynamic_config(GITLAB_URL, project_path)
                with open(config_path, 'w') as f:
                    f.write(dynamic_config)

            # Generate changelog
            result = generate_changelog(
                repo_path=repo_path,
                config_path=config_path,
                tag_range=data.get('tag_range'),
                unreleased=data.get('unreleased', False),
                latest=data.get('latest', False),
                output_format=data.get('output_format', 'markdown')
            )

            # Response sesuai format
            if data.get('output_format') == 'json':
                return Response(result['changelog'], mimetype='application/json')
            else:
                return Response(result['changelog'], mimetype='text/markdown')

        finally:
            # Cleanup
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Error generating changelog: {str(e)}")
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500


@app.route('/api/v1/bump-version', methods=['POST'])
@require_auth
def bump_version():
    """
    Dapatkan versi bump berikutnya berdasarkan commits.

    Request body (JSON):
    {
        "project_path": "group/project",
        "gitlab_token": "glpat-xxx"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Bad Request', 'message': 'JSON body required'}), 400

        project_path = data.get('project_path')
        gitlab_token = data.get('gitlab_token')

        if not project_path or not gitlab_token:
            return jsonify({'error': 'Bad Request', 'message': 'project_path and gitlab_token are required'}), 400

        work_dir = tempfile.mkdtemp(prefix='changelog-', dir=WORK_DIR)

        try:
            repo_path = clone_repository(GITLAB_URL, project_path, gitlab_token, work_dir)

            # Generate config dinamis
            config_path = os.path.join(work_dir, 'cliff.toml')
            dynamic_config = get_dynamic_config(GITLAB_URL, project_path)
            with open(config_path, 'w') as f:
                f.write(dynamic_config)

            version = get_bumped_version(repo_path, config_path)

            return jsonify({
                'version': version,
                'project': project_path
            })

        finally:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Error getting bumped version: {str(e)}")
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500


@app.route('/api/v1/changelog/local', methods=['POST'])
@require_auth
def create_changelog_local():
    """
    Generate changelog dari repository yang sudah di-mount.
    Berguna jika repository sudah ada di server.

    Request body (JSON):
    {
        "repo_path": "/mnt/repos/myproject",   # Path ke repository lokal
        "tag_range": "v1.0.0..v2.0.0",
        "unreleased": false,
        "latest": false,
        "output_format": "markdown"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Bad Request', 'message': 'JSON body required'}), 400

        repo_path = data.get('repo_path')

        if not repo_path:
            return jsonify({'error': 'Bad Request', 'message': 'repo_path is required'}), 400

        if not os.path.exists(repo_path):
            return jsonify({'error': 'Not Found', 'message': f'Repository not found: {repo_path}'}), 404

        # Generate config dinamis
        work_dir = tempfile.mkdtemp(prefix='changelog-config-', dir=WORK_DIR)
        config_path = os.path.join(work_dir, 'cliff.toml')

        if data.get('config'):
            with open(config_path, 'w') as f:
                f.write(data['config'])
        else:
            # Gunakan project_path jika ada, atau extract dari repo_path
            project_path = data.get('project_path', os.path.basename(repo_path))
            dynamic_config = get_dynamic_config(GITLAB_URL, project_path)
            with open(config_path, 'w') as f:
                f.write(dynamic_config)

        try:
            result = generate_changelog(
                repo_path=repo_path,
                config_path=config_path,
                tag_range=data.get('tag_range'),
                unreleased=data.get('unreleased', False),
                latest=data.get('latest', False),
                output_format=data.get('output_format', 'markdown')
            )

            if data.get('output_format') == 'json':
                return Response(result['changelog'], mimetype='application/json')
            else:
                return Response(result['changelog'], mimetype='text/markdown')

        finally:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Error generating changelog from local repo: {str(e)}")
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500


@app.route('/api/v1/release-notes', methods=['POST'])
@require_auth
def create_release_notes():
    """
    Generate release notes untuk tag tertentu (shorthand untuk --latest).
    Cocok untuk GitLab Release.

    Request body (JSON):
    {
        "project_path": "group/project",
        "gitlab_token": "glpat-xxx",
        "tag": "v1.2.0"                        # Optional: specific tag
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Bad Request', 'message': 'JSON body required'}), 400

        project_path = data.get('project_path')
        gitlab_token = data.get('gitlab_token')

        if not project_path or not gitlab_token:
            return jsonify({'error': 'Bad Request', 'message': 'project_path and gitlab_token are required'}), 400

        work_dir = tempfile.mkdtemp(prefix='changelog-', dir=WORK_DIR)

        try:
            repo_path = clone_repository(GITLAB_URL, project_path, gitlab_token, work_dir)

            # Generate config dinamis atau gunakan custom
            config_path = os.path.join(work_dir, 'cliff.toml')
            if data.get('config'):
                with open(config_path, 'w') as f:
                    f.write(data['config'])
            else:
                dynamic_config = get_dynamic_config(GITLAB_URL, project_path)
                with open(config_path, 'w') as f:
                    f.write(dynamic_config)

            # Build command untuk release notes
            cmd = ['git-cliff', '--repository', repo_path, '--latest', '--config', config_path]

            # Specific tag jika diminta
            if data.get('tag'):
                cmd.extend(['--tag', data['tag']])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                raise Exception(f"git-cliff failed: {result.stderr}")

            return Response(result.stdout, mimetype='text/markdown')

        finally:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Error generating release notes: {str(e)}")
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500


if __name__ == '__main__':
    # Pastikan work directory ada
    os.makedirs(WORK_DIR, exist_ok=True)

    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'

    logger.info(f"Starting Changelog Service on port {port}")
    logger.info(f"GitLab URL: {GITLAB_URL}")
    app.run(host='0.0.0.0', port=port, debug=debug)
