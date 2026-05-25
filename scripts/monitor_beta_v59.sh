#!/usr/bin/env bash
# monitor_beta_v59.sh — ANSI dashboard from BetaV59 logs
# Usage:
#   Live local:   ./scripts/monitor_beta_v59.sh /path/to/beta_v59.log
#   Live remote:  ./scripts/monitor_beta_v59.sh ssh root@204.168.199.124
#   One-shot:     ssh root@IP 'tail -200 logs/beta_v59.log' | ./scripts/monitor_beta_v59.sh

LOG="${1:-}"
REFRESH=5

# ANSI
R="\033[0m"; B="\033[1m"; D="\033[2m"
RED="\033[31m"; GRN="\033[32m"; YLW="\033[33m"; BLU="\033[34m"; MAG="\033[35m"; CYN="\033[36m"
BGRED="\033[41m"; BGGRN="\033[42m"; BGYLW="\033[43m"

get_log() {
    if [[ -z "$LOG" ]]; then
        cat
    elif [[ "$LOG" == ssh* ]]; then
        $LOG "tail -300 /root/freqtrade/logs/beta_v59.log" 2>/dev/null
    else
        tail -300 "$LOG" 2>/dev/null
    fi
}

bar() {
    local score="$1" min="$2"
    awk -v s="$score" -v m="$min" 'BEGIN {
        w=20; f=int(s/0.6*w); if(f>w)f=w; if(f<0)f=0
        pass=(s>=m)
        for(i=0;i<f;i++) printf (pass?"\033[32m":"\033[2m") "█"
        for(i=f;i<w;i++) printf "\033[2m░"
        printf "\033[0m"
    }'
}

render() {
    local data
    data=$(get_log)
    [[ -z "$data" ]] && { echo "Waiting for log data..."; return; }

    # Parse QUEUE block
    local q_header q_long q_short
    q_header=$(echo "$data" | grep "QUEUE " | tail -1)
    q_long=$(echo "$data" | awk '/QUEUE /{found=1} found && /LONG QUEUE/{p=1;next} found && /SHORT QUEUE/{p=0} p && /^ *#/{print}' | tail -10)
    q_short=$(echo "$data" | awk '/QUEUE /{found=1} found && /SHORT QUEUE/{p=1;next} found && /^ *$/{p=0} p && /^ *#/{print}' | tail -10)

    local q_date regime btc_mom min_score
    # Header line contains "QUEUE 2026-..." not "LONG QUEUE" or "SHORT QUEUE"
    q_header=$(echo "$data" | grep "INFO - QUEUE " | tail -1)
    q_date=$(echo "$q_header" | grep -o 'QUEUE [0-9-]* [0-9:]*' | sed 's/QUEUE //')
    regime=$(echo "$q_header" | grep -o 'regime=[a-z]*' | sed 's/regime=//')
    btc_mom=$(echo "$q_header" | grep -o 'btc_mom=[0-9.-]*' | sed 's/btc_mom=//')
    min_score=$(echo "$q_header" | grep -o 'min_score=[0-9.]*' | sed 's/min_score=//')

    # Heartbeat
    local hb
    hb=$(echo "$data" | grep "heartbeat" | tail -1 | grep -o '[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}')

    # Gate events
    local gates
    gates=$(echo "$data" | grep "GATE " | tail -8)

    # Trade events
    local trades
    trades=$(echo "$data" | grep -E "EXIT |CLOSE " | tail -6)

    # Stake
    local stake_line
    stake_line=$(echo "$data" | grep "STAKE " | tail -1)

    # Regime color
    local rc
    case "$regime" in
        bull)    rc="${BGGRN}${B} BULL ${R}" ;;
        bear)    rc="${BGRED}${B} BEAR ${R}" ;;
        ranging) rc="${BGYLW}${B} RANG ${R}" ;;
        *)       rc="${D} ??? ${R}" ;;
    esac

    printf "\033[2J\033[H"

    # Header
    printf "${B}${CYN}══════════════════════════════════════════════════════════════════════${R}\n"
    printf "${B}${CYN}  BetaV59 Monitor${R}  ${D}%s${R}  ${D}hb:%s${R}\n" "$q_date" "$hb"
    printf "${B}${CYN}══════════════════════════════════════════════════════════════════════${R}\n"
    printf "\n  Regime: %b  BTC Mom: ${B}%s${R}  Min Score: ${B}%s${R}\n" "$rc" "$btc_mom" "$min_score"

    # Queue renderer
    render_queue() {
        local title="$1" color="$2" lines="$3"
        printf "\n${B}%b  %s${R}\n" "$color" "$title"
        printf "  ${D}%-4s %-6s %-7s %-14s %-7s %-5s  %-20s${R}\n" "#" "Pair" "Adj" "Raw*Mult" "BZ" "Vol" ""
        printf "  ${D}─────────────────────────────────────────────────────────────────${R}\n"
        if [[ -z "$lines" ]]; then
            printf "  ${D}(empty)${R}\n"
            return
        fi
        echo "$lines" | while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local rk pr adj raw mult bz vol
            rk=$(echo "$line" | awk '{print $1}')
            pr=$(echo "$line" | awk '{print $2}')
            adj=$(echo "$line" | sed 's/.*adj=\([0-9.-]*\).*/\1/')
            raw=$(echo "$line" | sed 's/.*(raw=\([0-9.]*\).*/\1/')
            mult=$(echo "$line" | sed 's/.*\*\([0-9.]*\)).*/\1/')
            bz=$(echo "$line" | sed 's/.*bz=\([0-9.-]*\).*/\1/')
            vol=$(echo "$line" | sed 's/.*vol=\([0-9.]*\).*/\1/')

            local flag=""
            echo "$line" | grep -q "PASS" && flag="${BGGRN}${B} GO ${R}"
            local pc="${R}"
            [[ "$pr" == "BTC" ]] && pc="${D}"

            printf "  ${B}%-4s${R} %b%-6s%b %b%-7s%b %-14s %-7s %-5s " \
                "$rk" "$pc" "$pr" "$R" \
                "$(awk -v a="$adj" -v m="${min_score:-0.45}" 'BEGIN{printf (a>=m)?"\033[32m":"\033[0m"}')" "$adj" "$R" \
                "${raw}*${mult}" "$bz" "$vol"
            bar "$adj" "${min_score:-0.45}"
            printf " %b\n" "$flag"
        done
    }

    render_queue "▲ LONG QUEUE" "$GRN" "$q_long"
    render_queue "▼ SHORT QUEUE" "$RED" "$q_short"

    # Gate
    printf "\n${B}${MAG}  ⚡ GATE (last 8)${R}\n"
    printf "  ${D}─────────────────────────────────────────────────────────────────${R}\n"
    if [[ -n "$gates" ]]; then
        echo "$gates" | while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local ts pr sd
            ts=$(echo "$line" | grep -o '[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}')
            pr=$(echo "$line" | sed 's/.*GATE \([^ ]*\).*/\1/' | sed 's|/USDC:USDC||')
            sd=$(echo "$line" | awk -F'GATE [^ ]* ' '{print $2}' | awk -F' ' '{print $1}')

            if echo "$line" | grep -q "ACCEPT"; then
                local sc=$(echo "$line" | sed 's/.*score=\([0-9.]*\).*/\1/')
                printf "  ${GRN}✓${R} ${D}%s${R} ${B}%-5s${R} %-5s ${GRN}ACCEPT${R} score=%s\n" "$ts" "$pr" "$sd" "$sc"
            elif echo "$line" | grep -q "beaten"; then
                local by=$(echo "$line" | sed 's/.*beaten by \([^ ]*\).*/\1/' | sed 's|/USDC:USDC||')
                printf "  ${YLW}↓${R} ${D}%s${R} %-5s %-5s ${YLW}#2+ beaten by %s${R}\n" "$ts" "$pr" "$sd" "$by"
            elif echo "$line" | grep -q "score="; then
                local sc=$(echo "$line" | sed 's/.*score=\([0-9.]*\).*/\1/')
                printf "  ${RED}✗${R} ${D}%s${R} %-5s %-5s ${RED}low ${R}%s\n" "$ts" "$pr" "$sd" "$sc"
            elif echo "$line" | grep -q "max_pos"; then
                printf "  ${RED}■${R} ${D}%s${R} %-5s %-5s ${RED}full${R}\n" "$ts" "$pr" "$sd"
            elif echo "$line" | grep -q "already"; then
                printf "  ${D}· %s %-5s %-5s dup${R}\n" "$ts" "$pr" "$sd"
            else
                printf "  ${D}? %s %s${R}\n" "$ts" "$pr"
            fi
        done
    else
        printf "  ${D}(waiting)${R}\n"
    fi

    # Trades
    printf "\n${B}${BLU}  📊 TRADES (last 6)${R}\n"
    printf "  ${D}─────────────────────────────────────────────────────────────────${R}\n"
    if [[ -n "$trades" ]]; then
        echo "$trades" | while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local ts
            ts=$(echo "$line" | grep -o '[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}')
            if echo "$line" | grep -q "CLOSE"; then
                local pr sd pft pnl bal rsn
                pr=$(echo "$line" | sed 's/.*CLOSE \([^ ]*\).*/\1/' | sed 's|/USDC:USDC||')
                sd=$(echo "$line" | grep -o 'LONG\|SHORT')
                pft=$(echo "$line" | sed 's/.*profit=\([0-9.-]*\)%.*/\1/')
                pnl=$(echo "$line" | sed 's/.*pnl=\$\([0-9.-]*\).*/\1/')
                bal=$(echo "$line" | sed 's/.*balance=\$\([0-9.-]*\).*/\1/')
                rsn=$(echo "$line" | sed 's/.*reason=\([^ ]*\).*/\1/')
                local c="${GRN}"; echo "$pnl" | grep -q "^-" && c="${RED}"
                printf "  %b●%b ${D}%s${R} ${B}%-5s${R} %-5s %b%+6.2f%% \$%s%b  bal=\$%s  ${D}%s${R}\n" \
                    "$c" "$R" "$ts" "$pr" "$sd" "$c" "$pft" "$pnl" "$R" "$bal" "$rsn"
            elif echo "$line" | grep -q "EXIT"; then
                local pr rsn pft
                pr=$(echo "$line" | sed 's/.*EXIT \([^ ]*\).*/\1/' | sed 's|/USDC:USDC||')
                rsn=$(echo "$line" | sed 's/.*reason=\([^ ]*\).*/\1/')
                pft=$(echo "$line" | sed 's/.*profit=\([0-9.-]*\)%.*/\1/')
                local c="${GRN}"; echo "$pft" | grep -q "^-" && c="${RED}"
                printf "  ${D}→ %s${R} %-5s %b%s %+.2f%%%b\n" "$ts" "$pr" "$c" "$rsn" "$pft" "$R"
            fi
        done
    else
        printf "  ${D}(no trades yet)${R}\n"
    fi

    # Stake
    if [[ -n "$stake_line" ]]; then
        local sv sl so
        sv=$(echo "$stake_line" | sed 's/.*stake=\$\([0-9.]*\).*/\1/')
        sl=$(echo "$stake_line" | sed 's/.*lev=\([0-9.]*\)x.*/\1/')
        so=$(echo "$stake_line" | sed 's/.*open=\([0-9]*\).*/\1/')
        printf "\n  ${D}Stake: \$%s | Lev: %sx | Open: %s/4${R}\n" "$sv" "$sl" "$so"
    fi

    printf "\n${D}  %s | refresh %ds | Ctrl+C to exit${R}\n" "$(date '+%H:%M:%S')" "$REFRESH"
}

# Stdin mode (one-shot)
if [[ -z "$LOG" ]]; then
    LOG="" render
    exit 0
fi

# Live loop
while true; do
    render
    sleep "$REFRESH"
done
