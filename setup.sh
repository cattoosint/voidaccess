#!/usr/bin/env bash
# VoidAccess Interactive Setup Wizard
# Works on macOS (zsh/bash), Ubuntu/Debian (bash), and Windows Git Bash/WSL

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_ok() { echo "${GREEN}✓${NC} $1"; }
print_fail() { echo "${RED}✗${NC} $1"; }
print_warn() { echo "${YELLOW}⚠${NC} $1"; }
print_info() { echo "${BLUE}→${NC} $1"; }
print_step() { echo ""; echo "${CYAN}${BOLD}━━━ STEP $1 ━━━${NC}"; }
prompt() { echo -n "${BLUE}▸${NC} $1"; }

_prompt() {
    local prompt_text="$1"
    local default="$2"
    if [ ! -t 0 ]; then
        echo "${default}"
        return
    fi
    read -r -p "$prompt_text" answer || answer="$default"
    echo "${answer:-$default}"
}

env_update() {
    local key="$1"
    local value="$2"
    local env_file="$SCRIPT_DIR/.env"

    if grep -q "^${key}=" "$env_file" 2>/dev/null; then
        if sed -i "s|^${key}=.*|${key}=${value}|" "$env_file" 2>/dev/null; then
            :
        else
            python3 -c "
import re
with open('$env_file', 'r') as f:
    content = f.read()
content = re.sub(r'^${key}=.*', '${key}=${value}', content, flags=re.MULTILINE)
with open('$env_file', 'w') as f:
    f.write(content)
"
        fi
    else
        echo "${key}=${value}" >> "$env_file"
    fi
}

env_append() {
    local line="$1"
    local env_file="$SCRIPT_DIR/.env"
    echo "$line" >> "$env_file"
}

wait_for_key() {
    local prompt_text="$1"
    local default="${2:-}"
    local yn_default=""
    if [ "$default" = "Y" ] || [ "$default" = "y" ]; then
        yn_default="Y/n"
    elif [ "$default" = "N" ] || [ "$default" = "n" ]; then
        yn_default="y/N"
    else
        yn_default="y/n"
    fi
    local response=""
    echo ""
    prompt "$prompt_text [$yn_default]: "
    response="$(_prompt "" "$default")"
    echo "$response"
}

# =============================================================================
# STEP 1: Prerequisites Check
# =============================================================================
print_step "1" "Prerequisites Check"
echo ""

check_cmd() {
    if command -v "$1" >/dev/null 2>&1; then
        print_ok "$1 found: $($1 --version 2>/dev/null | head -n1 | cut -d' ' -f1-2 || echo "installed")"
        return 0
    else
        print_fail "$1 not found"
        return 1
    fi
}

check_python() {
    if python3 --version > /dev/null 2>&1; then
        PY_CMD="python3"
    elif python --version > /dev/null 2>&1; then
        PY_CMD="python"
    else
        PY_CMD=""
    fi

    if [ -n "$PY_CMD" ]; then
        if ! $PY_CMD -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" > /dev/null 2>&1; then
            PY_CMD=""
        fi
    fi

    if [ -n "$PY_CMD" ]; then
        echo -e "${GREEN}✓ Python ($PY_CMD)${NC}"
    else
        echo -e "${YELLOW}⚠ Python 3.8+ not found${NC}"
        echo "  Secret generation will use /dev/urandom fallback"
    fi
}

DOCKER_OK=false
DOCKER_COMPOSE_OK=false
TOR_OK=false
PYTHON_OK=false
GIT_OK=false

if [ ! -t 0 ]; then
    echo -e "${YELLOW}Warning: Non-interactive mode detected. Using defaults for all prompts.${NC}"
fi

if check_cmd docker; then
    DOCKER_OK=true
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    print_ok "docker compose v$(docker compose version 2>/dev/null | grep -oP 'v\K[0-9.]+' | head -1 || 'available')"
    DOCKER_COMPOSE_OK=true
else
    if command -v docker-compose >/dev/null 2>&1; then
        print_ok "docker-compose installed"
        DOCKER_COMPOSE_OK=true
    else
        print_fail "docker compose not found"
    fi
fi

check_cmd tor >/dev/null 2>&1 && TOR_OK=true || print_warn "Tor not found (optional, for non-Docker setup)"
check_python
[ -n "$PY_CMD" ] && PYTHON_OK=true
check_cmd git && GIT_OK=true

echo ""
if [ "$DOCKER_OK" = false ]; then
    print_fail "Docker is required to run VoidAccess."
    echo ""
    echo "Install Docker:"
    echo "  macOS:    brew install --cask docker"
    echo "  Ubuntu:   sudo apt install docker.io docker-compose"
    echo "  Windows:  https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    exit 1
fi

if [ "$PYTHON_OK" = false ]; then
    print_warn "Python not found — will use Docker for all services."
fi

if [ "$GIT_OK" = false ]; then
    print_warn "Git not found — cannot verify source version."
fi

# =============================================================================
# STEP 2: Environment File Setup
# =============================================================================
print_step "2" "Environment File Setup"
echo ""

ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
OVERWRITE=false

if [ -f "$ENV_FILE" ]; then
    print_info "A .env file already exists."
    response="$(wait_for_key "Overwrite" "N")"
    if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
        OVERWRITE=true
        print_info "Overwriting existing .env"
    else
        print_info "Keeping existing .env — skipping configuration."
        echo ""
        print_warn "To re-run setup, delete or rename .env and run setup.sh again."
        exit 0
    fi
fi

if [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    print_ok "Created .env from .env.example"
else
    touch "$ENV_FILE"
    print_info "Created empty .env"
fi

# =============================================================================
# STEP 3: Generate Required Secrets
# =============================================================================
print_step "3" "Generate Required Secrets"
echo ""

if [ -n "$PY_CMD" ]; then
    JWT_SECRET=$($PY_CMD -c "import secrets; print(secrets.token_hex(32))")
    POSTGRES_PASSWORD=$($PY_CMD -c "import secrets; print(secrets.token_hex(16))")
else
    if [ -f /dev/urandom ]; then
        JWT_SECRET=$(cat /dev/urandom | tr -dc 'a-f0-9' | head -c 64)
        POSTGRES_PASSWORD=$(cat /dev/urandom | tr -dc 'a-f0-9' | head -c 32)
    else
        echo -e "${RED}Cannot generate secrets — install Python 3${NC}"
        exit 1
    fi
fi

env_update "JWT_SECRET" "$JWT_SECRET"
env_update "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
print_ok "Generated JWT_SECRET and POSTGRES_PASSWORD"

# =============================================================================
# STEP 4: LLM Provider Selection
# =============================================================================
print_step "4" "LLM Provider Selection"
echo ""
print_info "Choose your LLM provider (required for investigations):"
echo ""
echo "  ${BOLD}[1]${NC} Groq — FREE, fast, no credit card"
echo "           Llama 3.3 70B via Groq Cloud"
echo "           Sign up: https://console.groq.com"
echo ""
echo "  ${BOLD}[2]${NC} OpenRouter — FREE tier available"
echo "           100+ models including free options"
echo "           Sign up: https://openrouter.ai"
echo ""
echo "  ${BOLD}[3]${NC} Anthropic Claude — Paid, best quality"
echo "           Claude 3.5 Sonnet recommended"
echo "           Sign up: https://console.anthropic.com"
echo ""
echo "  ${BOLD}[4]${NC} OpenAI — Paid"
echo "           GPT-4o recommended"
echo "           Sign up: https://platform.openai.com"
echo ""
echo "  ${BOLD}[5]${NC} Google Gemini — FREE tier available"
echo "           Gemini 1.5 Flash/Pro"
echo "           Sign up: https://aistudio.google.com"
echo ""
echo "  ${BOLD}[6]${NC} Ollama — FREE, runs locally"
echo "           No internet needed. Install: https://ollama.ai"
echo ""
echo "  ${BOLD}[7]${NC} Skip — I'll configure this later"
echo ""

CHOICE=""
while true; do
    prompt "Enter choice [1-7]: "
    CHOICE="$(_prompt "" "1")"
    case "$CHOICE" in
        1|2|3|4|5|6|7) break ;;
        *) print_warn "Invalid choice. Please enter 1-7." ;;
    esac
done

test_api_key() {
    local provider="$1"
    local url="$2"
    local auth_header="$3"
    local key="$4"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $key" \
        "$url" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ]; then
        return 0
    else
        return 1
    fi
}

case "$CHOICE" in
    1)
        echo ""
        prompt "Enter your Groq API key: "
        GROQ_KEY="$(_prompt "" "")"
        if [ -n "$GROQ_KEY" ]; then
            print_info "Testing Groq API key..."
            if test_api_key "groq" "https://api.groq.com/openai/v1/models" "Bearer $GROQ_KEY" "$GROQ_KEY"; then
                env_update "GROQ_API_KEY" "$GROQ_KEY"
                print_ok "Groq API key valid"
            else
                print_warn "Key test failed (HTTP $HTTP_CODE)"
                response="$(wait_for_key "Save anyway" "N")"
                if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
                    env_update "GROQ_API_KEY" "$GROQ_KEY"
                    print_info "Saved (untested)"
                else
                    print_info "Key discarded"
                fi
            fi
        fi
        ;;
    2)
        echo ""
        prompt "Enter your OpenRouter API key: "
        OPENROUTER_KEY="$(_prompt "" "")"
        if [ -n "$OPENROUTER_KEY" ]; then
            print_info "Testing OpenRouter API key..."
            if test_api_key "openrouter" "https://openrouter.ai/api/v1/models" "Bearer $OPENROUTER_KEY" "$OPENROUTER_KEY"; then
                env_update "OPENROUTER_API_KEY" "$OPENROUTER_KEY"
                print_ok "OpenRouter API key valid"
            else
                print_warn "Key test failed (HTTP $HTTP_CODE)"
                response="$(wait_for_key "Save anyway" "N")"
                if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
                    env_update "OPENROUTER_API_KEY" "$OPENROUTER_KEY"
                    print_info "Saved (untested)"
                else
                    print_info "Key discarded"
                fi
            fi
        fi
        ;;
    3)
        echo ""
        prompt "Enter your Anthropic API key: "
        ANTHROPIC_KEY="$(_prompt "" "")"
        if [ -n "$ANTHROPIC_KEY" ]; then
            print_info "Testing Anthropic API key..."
            if test_api_key "anthropic" "https://api.anthropic.com/v1/models" "Bearer $ANTHROPIC_KEY" "$ANTHROPIC_KEY"; then
                env_update "ANTHROPIC_API_KEY" "$ANTHROPIC_KEY"
                print_ok "Anthropic API key valid"
            else
                print_warn "Key test failed (HTTP $HTTP_CODE)"
                response="$(wait_for_key "Save anyway" "N")"
                if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
                    env_update "ANTHROPIC_API_KEY" "$ANTHROPIC_KEY"
                    print_info "Saved (untested)"
                else
                    print_info "Key discarded"
                fi
            fi
        fi
        ;;
    4)
        echo ""
        prompt "Enter your OpenAI API key: "
        OPENAI_KEY="$(_prompt "" "")"
        if [ -n "$OPENAI_KEY" ]; then
            print_info "Testing OpenAI API key..."
            if test_api_key "openai" "https://api.openai.com/v1/models" "Bearer $OPENAI_KEY" "$OPENAI_KEY"; then
                env_update "OPENAI_API_KEY" "$OPENAI_KEY"
                print_ok "OpenAI API key valid"
            else
                print_warn "Key test failed (HTTP $HTTP_CODE)"
                response="$(wait_for_key "Save anyway" "N")"
                if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
                    env_update "OPENAI_API_KEY" "$OPENAI_KEY"
                    print_info "Saved (untested)"
                else
                    print_info "Key discarded"
                fi
            fi
        fi
        ;;
    5)
        echo ""
        prompt "Enter your Google AI API key: "
        GOOGLE_KEY="$(_prompt "" "")"
        if [ -n "$GOOGLE_KEY" ]; then
            print_info "Testing Google AI API key..."
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
                -H "Authorization: Bearer $GOOGLE_KEY" \
                "https://generativelanguage.googleapis.com/v1/models" 2>/dev/null || echo "000")
            if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "403" ]; then
                env_update "GOOGLE_API_KEY" "$GOOGLE_KEY"
                if [ "$HTTP_CODE" = "200" ]; then
                    print_ok "Google AI API key valid"
                else
                    print_ok "Google AI API key saved (403 = valid key, quota issue)"
                fi
            else
                print_warn "Key test failed (HTTP $HTTP_CODE)"
                response="$(wait_for_key "Save anyway" "N")"
                if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
                    env_update "GOOGLE_API_KEY" "$GOOGLE_KEY"
                    print_info "Saved (untested)"
                else
                    print_info "Key discarded"
                fi
            fi
        fi
        ;;
    6)
        print_info "Checking for Ollama..."
        OLLAMA_RESPONSE=$(curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null || echo "")
        if [ -n "$OLLAMA_RESPONSE" ] && echo "$OLLAMA_RESPONSE" | grep -q "models"; then
            print_ok "Ollama is running"
            echo ""
            print_info "Available models:"
            echo "$OLLAMA_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    if models:
        for m in models:
            name = m.get('name', 'unknown')
            size = m.get('size', 0)
            if size > 0:
                size_gb = size / (1024**3)
                print(f'  - {name} ({size_gb:.1f} GB)')
            else:
                print(f'  - {name}')
    else:
        print('  (no models found)')
except:
    print('  (could not parse model list)')
" 2>/dev/null || echo "  (could not list models)"
            echo ""
            env_update "OLLAMA_BASE_URL" "http://127.0.0.1:11434"
            print_ok "Ollama configured"
        else
            print_warn "Ollama is not running."
            echo ""
            print_info "To use Ollama:"
            echo "  1. Install: https://ollama.ai"
            echo "  2. Run: ollama serve"
            echo "  3. Pull a model: ollama pull llama3.2"
            echo "  4. Re-run setup.sh"
            echo ""
            env_append "# OLLAMA_BASE_URL=http://127.0.0.1:11434"
            print_info "Skipped for now (uncomment in .env after installing Ollama)"
        fi
        ;;
    7)
        env_append "# LLM provider: skipped — configure manually in .env"
        print_info "Skipped — configure your LLM provider manually in .env"
        ;;
esac

# =============================================================================
# STEP 5: Optional Enrichment Keys
# =============================================================================
print_step "5" "Optional Enrichment Keys"
echo ""
print_info "Threat intelligence enrichment keys"
print_info "(Press Enter to skip any)"
echo ""

prompt "AlienVault OTX API key (https://otx.alienvault.com): "
OTX_KEY="$(_prompt "" "")"
if [ -n "$OTX_KEY" ]; then
    print_info "Testing OTX API key..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "X-OTX-API-KEY: $OTX_KEY" \
        "https://otx.alienvault.com/api/v1/user/me" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        env_update "OTX_API_KEY" "$OTX_KEY"
        print_ok "OTX API key valid"
    else
        print_warn "Key test failed (HTTP $HTTP_CODE)"
        response="$(wait_for_key "Save anyway" "N")"
        if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
            env_update "OTX_API_KEY" "$OTX_KEY"
            print_info "Saved (untested)"
        else
            print_info "Key discarded"
        fi
    fi
fi

echo ""
prompt "VirusTotal API key (https://virustotal.com): "
VT_KEY="$(_prompt "" "")"
if [ -n "$VT_KEY" ]; then
    print_info "Testing VirusTotal API key..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "x-apikey: $VT_KEY" \
        "https://www.virustotal.com/api/v3/users/me" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        env_update "VT_API_KEY" "$VT_KEY"
        print_ok "VirusTotal API key valid"
    else
        print_warn "Key test failed (HTTP $HTTP_CODE)"
        response="$(wait_for_key "Save anyway" "N")"
        if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
            env_update "VT_API_KEY" "$VT_KEY"
            print_info "Saved (untested)"
        else
            print_info "Key discarded"
        fi
    fi
fi

# =============================================================================
# STEP 6: Redis Configuration
# =============================================================================
print_step "6" "Redis Configuration (Optional)"
echo ""
print_info "Redis enables JWT token revocation and circuit breaker"
print_info "persistence. Recommended for production."
echo ""

response="$(wait_for_key "Is Redis available" "N")"
if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
    REDIS_URL="redis://localhost:6379/0"
    prompt "Redis URL [$REDIS_URL]: "
    REDIS_URL_INPUT="$(_prompt "" "$REDIS_URL")"
    REDIS_URL="${REDIS_URL_INPUT:-$REDIS_URL}"

    print_info "Testing Redis..."
    REDIS_TEST=$(redis-cli -u "$REDIS_URL" ping 2>/dev/null || echo "FAIL")
    if [ "$REDIS_TEST" = "PONG" ]; then
        env_update "REDIS_URL" "$REDIS_URL"
        print_ok "Redis connection successful"
    else
        print_warn "Redis ping failed — check your Redis URL"
        response="$(wait_for_key "Save anyway" "N")"
        if [ "$response" = "Y" ] || [ "$response" = "y" ]; then
            env_update "REDIS_URL" "$REDIS_URL"
            print_info "Saved (untested)"
        fi
    fi
else
    print_info "OK — running without Redis."
    print_info "Logout may not immediately invalidate tokens."
fi

# =============================================================================
# STEP 7: Pre-seed MITRE ATT&CK Cache
# =============================================================================
print_step "7" "MITRE ATT&CK Cache"
echo ""
print_info "Pre-seeding MITRE ATT&CK database (~33MB, one-time download)"
print_info "This improves threat actor enrichment quality."
echo ""

response="$(wait_for_key "Download MITRE ATT&CK now" "Y")"
if [ "$response" != "N" ] && [ "$response" != "n" ]; then
    print_info "Downloading MITRE ATT&CK STIX data..."
    MITRE_TMP="/tmp/voidaccess_mitre_attack.json"

    if python3 -c "
import urllib.request
url = 'https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json'
urllib.request.urlretrieve(url, '$MITRE_TMP')
print('done')
" 2>/dev/null; then
        if [ -f "$MITRE_TMP" ]; then
            if [ -d "$SCRIPT_DIR/cti_data" ] || mkdir -p "$SCRIPT_DIR/cti_data" 2>/dev/null; then
                cp "$MITRE_TMP" "$SCRIPT_DIR/cti_data/enterprise-attack.json"
                rm -f "$MITRE_TMP"
                print_ok "MITRE ATT&CK cache seeded"
            fi
        fi
    else
        print_warn "Download failed — will seed on first investigation"
    fi
fi

# =============================================================================
# STEP 8: Start the Stack
# =============================================================================
print_step "8" "Start VoidAccess"
echo ""
print_info "Ready to start VoidAccess?"
echo ""
echo "  Services: PostgreSQL, Tor, FastAPI, Next.js"
echo "  This will take 3-5 minutes on first run."
echo ""

response="$(wait_for_key "Start now" "Y")"
if [ "$response" = "N" ] || [ "$response" = "n" ]; then
    print_info "OK — start manually with: docker compose up --build -d"
    exit 0
fi

print_info "Building and starting containers..."
echo ""

DOCKER_BUILDKIT=1 docker compose up --build -d

print_info "Waiting for services to be ready..."
echo -n "  "

for i in $(seq 1 60); do
    STATUS=$(curl -s --max-time 5 http://localhost:8000/healthz/ready 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || echo "")
    if [ "$STATUS" = "ready" ]; then
        echo ""
        print_ok "VoidAccess is ready"
        break
    fi
    echo -n "."
    sleep 5
done

if [ "$STATUS" != "ready" ]; then
    echo ""
    print_warn "Services may still be starting. Check status with:"
    echo "  docker compose ps"
    echo "  docker compose logs -f"
fi

# =============================================================================
# STEP 9: Summary
# =============================================================================
echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║        VoidAccess is ready!                          ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  UI:      http://localhost:3000                     ║"
echo "║  API:     http://localhost:8000                     ║"
echo "║  Docs:    http://localhost:8000/docs                ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  Default login:                                    ║"
echo "║  Email:    admin@voidaccess.tech                    ║"
echo "║  Password: (set during first login)                 ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  To add API keys later:                            ║"
echo "║  → Settings page in the UI                         ║"
echo "║  → Or re-run: bash setup.sh                        ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""