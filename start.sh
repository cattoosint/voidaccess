#!/usr/bin/env bash
set -e

# Colors
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
NC=$'\033[0m'

# Spinner function
spin() {
    local pid=$1
    local msg="$2"
    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    tput civis 2>/dev/null || true
    while kill -0 "$pid" 2>/dev/null; do
        local frame="${frames:$i:1}"
        printf "\r  ${CYAN}%s${NC}  %s" \
            "$frame" "$msg"
        i=$(( (i + 1) % 10 ))
        sleep 0.1
    done
    tput cnorm 2>/dev/null || true
    printf "\r%-60s\r" " "
}

# Docker permission check
if ! docker info > /dev/null 2>&1; then
    if sudo docker info > /dev/null 2>&1; then
        printf "\n  ${YELLOW}⚠${NC}  "
        printf "Docker requires sudo.\n"
        printf "  ${DIM}→${NC}  Re-run with: "
        printf "${BOLD}sudo bash start.sh${NC}\n\n"
        exit 1
    else
        printf "\n  ${RED}✗${NC}  "
        printf "Docker not running or not installed.\n"
        exit 1
    fi
fi

# Check .env exists
if [ ! -f .env ]; then
    printf "\n  ${RED}✗${NC}  .env not found.\n"
    printf "  ${DIM}→${NC}  Run setup first: "
    printf "${BOLD}bash setup.sh${NC}\n\n"
    exit 1
fi

# Check JWT_SECRET is not weak
JWT=$(grep "^JWT_SECRET=" .env 2>/dev/null \
    | cut -d= -f2-)
if [ -z "$JWT" ] || [ ${#JWT} -lt 32 ]; then
    printf "\n  ${RED}✗${NC}  JWT_SECRET missing "
    printf "or too short.\n"
    printf "  ${DIM}→${NC}  Re-run: "
    printf "${BOLD}bash setup.sh${NC}\n\n"
    exit 1
fi

# Banner
printf "\n"
printf "  ${CYAN}╔═══════════════════════════════════╗${NC}\n"
printf "  ${CYAN}║${NC}  ${BOLD}VoidAccess${NC}  ·  Starting up       "
printf "${CYAN}║${NC}\n"
printf "  ${CYAN}╚═══════════════════════════════════╝${NC}\n\n"

# Determine docker-compose file location
COMPOSE_FILE="infra/docker-compose.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    COMPOSE_FILE="docker-compose.yml"
fi

COMPOSE_CMD="docker compose -f $COMPOSE_FILE \
    --project-directory ."

# Build and start - FOREGROUND with output hidden
printf "  ${DIM}→${NC}  Building containers"
printf " (first run: 3-5 min, cached after)...\n\n"

$COMPOSE_CMD up --build \
    > /tmp/va_start.log 2>&1
BUILD_EXIT=$?

if [ $BUILD_EXIT -ne 0 ]; then
    printf "  ${RED}✗${NC}  Build failed.\n"
    printf "  ${DIM}→${NC}  Last 20 lines of output:\n\n"
    tail -20 /tmp/va_start.log | \
        sed 's/^/      /'
    printf "\n  ${DIM}→${NC}  Full log: "
    printf "/tmp/va_start.log\n\n"
    exit 1
fi

printf "  ${GREEN}✓${NC}  Build complete\n\n"

# Wait for each service to become healthy
printf "  ${DIM}→${NC}  Waiting for services...\n\n"

SERVICES=("postgres" "tor" "fastapi" "nextjs")
LABELS=("PostgreSQL" "Tor" "FastAPI" "Next.js")
ALL_HEALTHY=true

for i in "${!SERVICES[@]}"; do
    SVC="${SERVICES[$i]}"
    LABEL="${LABELS[$i]}"
    HEALTHY=false

    for attempt in $(seq 1 60); do
        # Check container exists first
        if ! docker inspect \
           "voidaccess-${SVC}" \
           > /dev/null 2>&1; then
            sleep 2
            continue
        fi

        STATE=$(docker inspect \
            --format='{{.State.Status}}' \
            "voidaccess-${SVC}" 2>/dev/null)
        HEALTH=$(docker inspect \
            --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
            "voidaccess-${SVC}" 2>/dev/null)

        # Container is good if:
        # - health check says healthy, OR
        # - running with no health check
        if [ "$HEALTH" = "healthy" ] || \
           { [ "$STATE" = "running" ] && \
             [ "$HEALTH" = "none" ]; }; then
            printf "  ${GREEN}✓${NC}  $LABEL\n"
            HEALTHY=true
            break
        fi

        # Show waiting indicator
        printf "\r  ${CYAN}·${NC}  $LABEL — "
        printf "waiting (${attempt}/60)...   "
        sleep 3
    done

    # Clear the waiting line
    printf "\r%-60s\r" " "

    if [ "$HEALTHY" = "false" ]; then
        printf "  ${YELLOW}⚠${NC}  $LABEL — "
        printf "not healthy after 3 minutes\n"
        ALL_HEALTHY=false
    fi
done

printf "\n"

if [ "$ALL_HEALTHY" = "false" ]; then
    printf "  ${YELLOW}⚠${NC}  Some services are slow.\n"
    printf "  ${DIM}→${NC}  Check logs:\n"
    printf "       ${DIM}sudo docker compose -f "
    printf "$COMPOSE_FILE --project-directory "
    printf ". logs -f${NC}\n\n"
else
    # Ready banner
    printf "  ${GREEN}╔═══════════════════════════════════╗${NC}\n"
    printf "  ${GREEN}║${NC}                                   "
    printf "${GREEN}║${NC}\n"
    printf "  ${GREEN}║${NC}   ${GREEN}✓${NC}  ${BOLD}VoidAccess is ready!${NC}         "
    printf "${GREEN}║${NC}\n"
    printf "  ${GREEN}║${NC}                                   "
    printf "${GREEN}║${NC}\n"
    printf "  ${GREEN}╠═══════════════════════════════════╣${NC}\n"
    printf "  ${GREEN}║${NC}  UI   →  http://localhost:3001   "
    printf "${GREEN}║${NC}\n"
    printf "  ${GREEN}║${NC}  API  →  http://localhost:8000   "
    printf "${GREEN}║${NC}\n"
    printf "  ${GREEN}║${NC}  Docs →  http://localhost:8000/docs "
    printf "${GREEN}║${NC}\n"
    printf "  ${GREEN}╚═══════════════════════════════════╝${NC}\n\n"
fi