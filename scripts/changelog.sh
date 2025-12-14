#!/bin/bash
# ============================================
# Changelog Helper Script
# ============================================
# Script helper untuk memanggil Changelog Service dari shell runner
#
# USAGE:
#   ./changelog.sh <command> [options]
#
# COMMANDS:
#   full        - Generate full changelog
#   latest      - Generate release notes for latest tag
#   unreleased  - Generate unreleased changes
#   bump        - Get next version based on commits
#   release     - Create GitLab Release with notes
#
# ENVIRONMENT VARIABLES (required):
#   CHANGELOG_SERVICE_URL - URL of changelog service
#   CHANGELOG_API_TOKEN   - API token for authentication
#   GITLAB_TOKEN          - GitLab personal access token
#   CI_PROJECT_PATH       - GitLab project path (group/project)
#
# EXAMPLES:
#   ./changelog.sh full
#   ./changelog.sh latest --tag v1.2.0
#   ./changelog.sh release --tag v1.2.0
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
CHANGELOG_SERVICE_URL="${CHANGELOG_SERVICE_URL:-http://localhost:8080}"
OUTPUT_FILE=""
TAG=""
FORMAT="markdown"

# Functions
print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

check_required_vars() {
    local missing=0

    if [ -z "$CHANGELOG_API_TOKEN" ]; then
        print_error "CHANGELOG_API_TOKEN is not set"
        missing=1
    fi

    if [ -z "$GITLAB_TOKEN" ]; then
        print_error "GITLAB_TOKEN is not set"
        missing=1
    fi

    if [ -z "$CI_PROJECT_PATH" ]; then
        print_error "CI_PROJECT_PATH is not set"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        echo "Required environment variables:"
        echo "  CHANGELOG_SERVICE_URL  - URL of changelog service (default: http://localhost:8080)"
        echo "  CHANGELOG_API_TOKEN    - API token for authentication"
        echo "  GITLAB_TOKEN           - GitLab personal access token"
        echo "  CI_PROJECT_PATH        - GitLab project path (e.g., group/project)"
        exit 1
    fi
}

usage() {
    cat << EOF
Changelog Helper Script

USAGE:
    $0 <command> [options]

COMMANDS:
    full        Generate full changelog from all tags
    latest      Generate release notes for latest/specific tag
    unreleased  Generate changelog for unreleased changes
    bump        Get next version based on conventional commits
    release     Create GitLab Release with auto-generated notes

OPTIONS:
    -o, --output FILE    Output file (default: stdout or CHANGELOG.md)
    -t, --tag TAG        Specific tag for release notes
    -f, --format FORMAT  Output format: markdown or json (default: markdown)
    -h, --help           Show this help message

EXAMPLES:
    $0 full -o CHANGELOG.md
    $0 latest --tag v1.2.0
    $0 bump
    $0 release --tag v1.2.0

ENVIRONMENT VARIABLES:
    CHANGELOG_SERVICE_URL  URL of changelog service
    CHANGELOG_API_TOKEN    API token for authentication
    GITLAB_TOKEN           GitLab personal access token
    CI_PROJECT_PATH        GitLab project path (group/project)
EOF
}

api_call() {
    local endpoint="$1"
    local data="$2"

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "${CHANGELOG_SERVICE_URL}${endpoint}" \
        -H "Content-Type: application/json" \
        -H "X-API-Token: ${CHANGELOG_API_TOKEN}" \
        -d "$data")

    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        print_error "API call failed (HTTP $http_code)"
        echo "$body" >&2
        exit 1
    fi

    echo "$body"
}

cmd_full() {
    check_required_vars
    print_info "Generating full changelog for ${CI_PROJECT_PATH}..."

    local data="{
        \"project_path\": \"${CI_PROJECT_PATH}\",
        \"gitlab_token\": \"${GITLAB_TOKEN}\",
        \"output_format\": \"${FORMAT}\"
    }"

    local result
    result=$(api_call "/api/v1/changelog" "$data")

    if [ -n "$OUTPUT_FILE" ]; then
        echo "$result" > "$OUTPUT_FILE"
        print_success "Changelog saved to $OUTPUT_FILE"
    else
        echo "$result"
    fi
}

cmd_latest() {
    check_required_vars
    print_info "Generating release notes..."

    local data="{
        \"project_path\": \"${CI_PROJECT_PATH}\",
        \"gitlab_token\": \"${GITLAB_TOKEN}\"
    }"

    if [ -n "$TAG" ]; then
        data="{
            \"project_path\": \"${CI_PROJECT_PATH}\",
            \"gitlab_token\": \"${GITLAB_TOKEN}\",
            \"tag\": \"${TAG}\"
        }"
    fi

    local result
    result=$(api_call "/api/v1/release-notes" "$data")

    if [ -n "$OUTPUT_FILE" ]; then
        echo "$result" > "$OUTPUT_FILE"
        print_success "Release notes saved to $OUTPUT_FILE"
    else
        echo "$result"
    fi
}

cmd_unreleased() {
    check_required_vars
    print_info "Generating unreleased changes..."

    local data="{
        \"project_path\": \"${CI_PROJECT_PATH}\",
        \"gitlab_token\": \"${GITLAB_TOKEN}\",
        \"unreleased\": true,
        \"output_format\": \"${FORMAT}\"
    }"

    local result
    result=$(api_call "/api/v1/changelog" "$data")

    if [ -n "$OUTPUT_FILE" ]; then
        echo "$result" > "$OUTPUT_FILE"
        print_success "Unreleased changes saved to $OUTPUT_FILE"
    else
        echo "$result"
    fi
}

cmd_bump() {
    check_required_vars
    print_info "Getting next version..."

    local data="{
        \"project_path\": \"${CI_PROJECT_PATH}\",
        \"gitlab_token\": \"${GITLAB_TOKEN}\"
    }"

    local result
    result=$(api_call "/api/v1/bump-version" "$data")

    local version
    version=$(echo "$result" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$OUTPUT_FILE" ]; then
        echo "$version" > "$OUTPUT_FILE"
        print_success "Next version: $version (saved to $OUTPUT_FILE)"
    else
        print_success "Next version: $version"
    fi
}

cmd_release() {
    check_required_vars

    if [ -z "$TAG" ]; then
        print_error "Tag is required for release. Use --tag <tag>"
        exit 1
    fi

    if [ -z "$CI_API_V4_URL" ]; then
        CI_API_V4_URL="${GITLAB_URL:-https://gitlab.example.com}/api/v4"
    fi

    if [ -z "$CI_PROJECT_ID" ]; then
        print_error "CI_PROJECT_ID is not set"
        exit 1
    fi

    print_info "Creating GitLab Release for tag ${TAG}..."

    # Generate release notes first
    local notes_data="{
        \"project_path\": \"${CI_PROJECT_PATH}\",
        \"gitlab_token\": \"${GITLAB_TOKEN}\",
        \"tag\": \"${TAG}\"
    }"

    local notes
    notes=$(api_call "/api/v1/release-notes" "$notes_data")

    # Escape for JSON
    local notes_escaped
    notes_escaped=$(echo "$notes" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

    # Create GitLab Release
    local release_response
    release_response=$(curl -s --request POST \
        --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
        --header "Content-Type: application/json" \
        --data "{
            \"tag_name\": \"${TAG}\",
            \"name\": \"Release ${TAG}\",
            \"description\": ${notes_escaped}
        }" \
        "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/releases")

    if echo "$release_response" | grep -q '"tag_name"'; then
        print_success "GitLab Release created for ${TAG}"
    else
        print_error "Failed to create GitLab Release"
        echo "$release_response" >&2
        exit 1
    fi
}

# Parse arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        full|latest|unreleased|bump|release)
            COMMAND="$1"
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -f|--format)
            FORMAT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Execute command
case $COMMAND in
    full)
        cmd_full
        ;;
    latest)
        cmd_latest
        ;;
    unreleased)
        cmd_unreleased
        ;;
    bump)
        cmd_bump
        ;;
    release)
        cmd_release
        ;;
    "")
        print_error "No command specified"
        usage
        exit 1
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
