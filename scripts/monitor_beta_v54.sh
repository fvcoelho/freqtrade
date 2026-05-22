#!/usr/bin/env bash
# monitor_beta_v54.sh — ANSI dashboard from BetaV54 logs
# Usage:
#   Live local:   ./scripts/monitor_beta_v54.sh /path/to/beta_v54.log
#   Live remote:  ./scripts/monitor_beta_v54.sh ssh root@204.168.199.124
#   One-shot:     tail -300 logs/beta_v54.log | ./scripts/monitor_beta_v54.sh

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
        $LOG "tail -400 /root/freqtrade/logs/beta_v54.log" 2>/dev/null
    else
        tail -400 "$LOG" 2>/dev/null
    fi
}

# Spread-z bar centered on 0, with marker on z_entry threshold (±1.55).
# Args: $1=value, $2=z_entry (positive threshold)
# Range: [-3, +3], width 30 chars. Center "│" at 0, "┊" at ±threshold.
spread_bar() {
    awk -v v="$1" -v th="$2" 'BEGIN {
        lo=-3; hi=3; w=30
        # Clamp
        x = v; if(x<lo)x=lo; if(x>hi)x=hi
        # Position in 0..w
        pos = int((x - lo) / (hi - lo) * w)
        if(pos<0)pos=0; if(pos>=w)pos=w-1
        # Threshold positions
        zero = int((0 - lo) / (hi - lo) * w)
        tpos_p = int((th - lo) / (hi - lo) * w)
        tpos_n = int((-th - lo) / (hi - lo) * w)
        # Color: red if |v| >= th, yellow if approaching (>=0.7*th), dim otherwise
        col = "\033[2m"
        absv = (v<0)?-v:v
        if (absv >= th) col = "\033[31m"
        else if (absv >= 0.7*th) col = "\033[33m"
        else col = "\033[2m"
        printf "["
        for (i=0; i<w; i++) {
            if (i == pos)        printf col "█\033[0m"
            else if (i == zero)  printf "\033[36m│\033[0m"
            else if (i == tpos_p || i == tpos_n) printf "\033[35m┊\033[0m"
            else                 printf "\033[2m─\033[0m"
        }
        printf "]"
    }'
}

# Per-pair z-score bar, range [-3, +3], width 20. Marker at ±pair_z_entry (0.9).
pair_z_bar() {
    awk -v v="$1" -v th="$2" 'BEGIN {
        lo=-3; hi=3; w=20
        x = v; if(x<lo)x=lo; if(x>hi)x=hi
        pos = int((x - lo) / (hi - lo) * w)
        if(pos<0)pos=0; if(pos>=w)pos=w-1
        zero = int((0 - lo) / (hi - lo) * w)
        tp_p = int((th - lo) / (hi - lo) * w)
        tp_n = int((-th - lo) / (hi - lo) * w)
        col = "\033[2m"
        absv = (v<0)?-v:v
        if (absv >= th) col = "\033[32m"
        else if (absv >= 0.7*th) col = "\033[33m"
        printf "["
        for (i=0; i<w; i++) {
            if (i == pos)        printf col "▒\033[0m"
            else if (i == zero)  printf "\033[36m│\033[0m"
            else if (i == tp_p || i == tp_n) printf "\033[35m┊\033[0m"
            else                 printf "\033[2m─\033[0m"
        }
        printf "]"
    }'
}

# Trades-filled bar:  [██░] 2/3
trades_bar() {
    awk -v n="$1" -v m="$2" 'BEGIN {
        for(i=0;i<n;i++) printf "\033[32m█\033[0m"
        for(i=n;i<m;i++) printf "\033[2m░\033[0m"
    }'
}

# Extract value after "key=" up to space, end of line, or close-bracket
field() {
    # $1 = key, $2 = input line; portable awk extractor
    echo "$2" | awk -v k="$1" '
        {
            n = index($0, k"=")
            if (n == 0) { print ""; exit }
            s = substr($0, n + length(k) + 1)
            # Cut at first space, comma, or close-bracket
            m = match(s, /[ ,\]]/)
            if (m > 0) s = substr(s, 1, m-1)
            print s
        }'
}

render() {
    local data
    data=$(get_log)
    [[ -z "$data" ]] && { echo "Waiting for log data..."; return; }

    # Latest CYCLE block — group by the most recent timestamp prefix (1s granularity)
    # so we get the 5 CYCLE lines of the same cycle (they fall within ~1s of each other).
    local last_cycle_ts cycles
    last_cycle_ts=$(echo "$data" | grep "V54 CYCLE" | tail -1 | awk '{print $1" "$2}' | cut -d, -f1)
    # Pull the most recent block of CYCLE lines (last 5, regardless of exact ts match)
    cycles=$(echo "$data" | grep "V54 CYCLE" | tail -5)

    local last_groups
    last_groups=$(echo "$data" | grep "V54 GROUPS" | tail -1)

    # Latest GATE/STAKE/LEV
    local gates stake lev trades
    gates=$(echo "$data" | grep "V54 GATE" | tail -5)
    stake=$(echo "$data" | grep "V54 STAKE" | tail -1)
    lev=$(echo "$data" | grep "V54 LEV" | tail -1)
    # Only true trade events — avoid startup noise ("use_exit_signal", "exit_pricing", etc.)
    trades=$(echo "$data" | grep -E "(V54 LOSS|V54 COOLDOWN|ADJUST_POS CALLED|profit_ratio|notify_enter_fill|notify_exit|Found open order)" \
        | grep -v "Strategy using" | grep -v "exit_pricing" | grep -v "use_exit_signal" | tail -5)

    # BTC summary (from BTC CYCLE line)
    local btc_line
    btc_line=$(echo "$data" | grep "V54 CYCLE BTC/USDC:USDC" | tail -1)
    local btc_mom btc_atrz btc_p btc_d btc_hv btc_ve regime spreadA spreadB zth dd hl
    btc_mom=$(echo "$btc_line" | sed -n 's/.*btc\[mom=\([+-][0-9.]*\).*/\1/p')
    btc_atrz=$(echo "$btc_line" | sed -n 's/.*atrz=\([+-][0-9.]*\).*/\1/p')
    btc_p=$(echo "$btc_line" | sed -n 's/.*p=\([0-9]\).*/\1/p')
    btc_d=$(echo "$btc_line" | sed -n 's/.* d=\([0-9]\).*/\1/p')
    btc_hv=$(echo "$btc_line" | sed -n 's/.*hv=\([0-9]\).*/\1/p')
    btc_ve=$(echo "$btc_line" | sed -n 's/.*ve=\([0-9]\).*/\1/p')
    regime=$(echo "$btc_line" | sed -n 's/.*regime=\([a-z]*\).*/\1/p')
    spreadA=$(echo "$btc_line" | sed -n 's/.*A=\([+-][0-9.]*\).*/\1/p')
    spreadB=$(echo "$btc_line" | sed -n 's/.*B=\([+-][0-9.]*\).*/\1/p')
    zth=$(echo "$btc_line" | sed -n 's/.*zth=\([0-9.]*\).*/\1/p')
    dd=$(echo "$btc_line" | sed -n 's/.*dd=\([0-9.]*\)%.*/\1/p')
    hl=$(echo "$btc_line" | sed -n 's/.*hl=\([0-9]*\).*/\1/p')
    [[ -z "$zth" ]] && zth="1.55"
    [[ -z "$dd" ]] && dd="0.0"

    # Group state
    local total_open total_max groupA_n groupA_max groupA_cd groupB_n groupB_max groupB_cd
    total_open=$(echo "$last_groups" | sed -n 's/.*open=\([0-9]*\)\/.*/\1/p')
    total_max=$(echo "$last_groups" | sed -n 's/.*open=[0-9]*\/\([0-9]*\).*/\1/p')
    groupA_n=$(echo "$last_groups" | sed -n 's/.*\[A: \([0-9]*\)\/[0-9]*.*/\1/p')
    groupA_max=$(echo "$last_groups" | sed -n 's/.*\[A: [0-9]*\/\([0-9]*\).*/\1/p')
    groupA_cd=$(echo "$last_groups" | sed -n 's/.*\[A:[^]]*cd=\([^]]*\)\].*/\1/p')
    groupB_n=$(echo "$last_groups" | sed -n 's/.*\[B: \([0-9]*\)\/[0-9]*.*/\1/p')
    groupB_max=$(echo "$last_groups" | sed -n 's/.*\[B: [0-9]*\/\([0-9]*\).*/\1/p')
    groupB_cd=$(echo "$last_groups" | sed -n 's/.*\[B:[^]]*cd=\([^]]*\)\].*/\1/p')

    : "${total_open:=?}"; : "${total_max:=?}"
    : "${groupA_n:=0}"; : "${groupA_max:=1}"; : "${groupA_cd:=-}"
    : "${groupB_n:=0}"; : "${groupB_max:=1}"; : "${groupB_cd:=-}"

    # Heartbeat
    local hb
    hb=$(echo "$data" | grep "heartbeat" | tail -1 | grep -o '[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}')

    # Regime color
    local rc
    case "$regime" in
        range)    rc="${BGGRN}${B} RANGE ${R}" ;;
        trend)    rc="${BGYLW}${B} TREND ${R}" ;;
        consol)   rc="${BGRED}${B} CONSOL ${R}" ;;
        *)        rc="${D}  ???   ${R}" ;;
    esac

    printf "\033[2J\033[H"

    # ────────────────────────── HEADER ──────────────────────────
    printf "${B}${CYN}══════════════════════════════════════════════════════════════════════════════${R}\n"
    printf "${B}${CYN}  BetaV54 Monitor${R}   ${D}%s${R}   ${D}hb:%s${R}\n" "$last_cycle_ts" "$hb"
    printf "${B}${CYN}══════════════════════════════════════════════════════════════════════════════${R}\n"
    printf "\n  Regime: %b   BTC mom=${B}%s${R} atrz=${B}%s${R}  pump=%s dump=%s hvol=%s ve=%s   Open: ${B}%s/%s${R}\n" \
        "$rc" "$btc_mom" "$btc_atrz" "$btc_p" "$btc_d" "$btc_hv" "$btc_ve" "$total_open" "$total_max"
    printf "  z_entry=±${B}%s${R}   DD=${B}%s%%${R}   half_life=${B}%s${R}\n" "$zth" "$dd" "${hl:--}"

    # ────────────────────────── GROUPS ──────────────────────────
    printf "\n${B}${BLU}  ▣ GROUP A${R}  ${D}(XRP vs SOL+LINK — LONG-only)${R}\n"
    printf "    trades  "
    trades_bar "$groupA_n" "$groupA_max"
    printf "  ${B}%s/%s${R}    cooldown: ${D}%s${R}\n" "$groupA_n" "$groupA_max" "$groupA_cd"
    printf "    spread_z = ${B}%-6s${R}  " "$spreadA"
    spread_bar "${spreadA:-0}" "$zth"
    printf "  ${D}(−3 … 0 … +3)${R}\n"

    printf "\n${B}${BLU}  ▣ GROUP B${R}  ${D}(BTC+SOL vs ETH — LONG+SHORT)${R}\n"
    printf "    trades  "
    trades_bar "$groupB_n" "$groupB_max"
    printf "  ${B}%s/%s${R}    cooldown: ${D}%s${R}\n" "$groupB_n" "$groupB_max" "$groupB_cd"
    printf "    spread_z = ${B}%-6s${R}  " "$spreadB"
    spread_bar "${spreadB:-0}" "$zth"
    printf "  ${D}(−3 … 0 … +3)${R}\n"

    # ────────────────────────── PAIRS ──────────────────────────
    printf "\n${B}${CYN}  ◆ PAIRS${R}\n"
    printf "  ${D}%-6s %-5s %7s  %-22s %-3s %-3s %-3s %-6s %s${R}\n" \
        "Pair" "Grp" "pair_z" "bar (±0.9)" "vok" "rok" "sok" "regime" "sig"
    printf "  ${D}──────────────────────────────────────────────────────────────────────────${R}\n"
    if [[ -n "$cycles" ]]; then
        echo "$cycles" | while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local pair grp pz vok rok sok rg sig
            pair=$(echo "$line" | sed -n 's|.*V54 CYCLE \([^ ]*\) .*|\1|p' | sed 's|/USDC:USDC||')
            grp=$(echo "$line" | sed -n 's/.*grp=\([A-Z,]*\) .*/\1/p')
            pz=$(echo "$line" | sed -n 's/.*pz=\([+-][0-9.]*\).*/\1/p')
            vok=$(echo "$line" | sed -n 's/.*vok=\([0-9]*\).*/\1/p')
            rok=$(echo "$line" | sed -n 's/.*rok=\([0-9]*\).*/\1/p')
            sok=$(echo "$line" | sed -n 's/.*sok=\([0-9]*\).*/\1/p')
            rg=$(echo "$line" | sed -n 's/.*regime=\([a-z]*\).*/\1/p')
            sig=$(echo "$line" | sed -n 's/.*sig=\([A-Za-z]*\).*/\1/p')

            local vc rc_ sc sigc
            [[ "$vok" == "1" ]] && vc="${GRN}1${R}" || vc="${RED}0${R}"
            [[ "$rok" == "1" ]] && rc_="${GRN}1${R}" || rc_="${RED}0${R}"
            [[ "$sok" == "1" ]] && sc="${GRN}1${R}" || sc="${RED}0${R}"
            case "$sig" in
                LONG)  sigc="${BGGRN}${B} LONG ${R}" ;;
                SHORT) sigc="${BGRED}${B} SHORT${R}" ;;
                *)     sigc="${D}  -  ${R}" ;;
            esac

            printf "  %-6s %-5s ${B}%7s${R}  " "$pair" "$grp" "$pz"
            pair_z_bar "${pz:-0}" "0.9"
            printf "  %b   %b   %b   ${D}%-6s${R}  %b\n" "$vc" "$rc_" "$sc" "$rg" "$sigc"
        done
    else
        printf "  ${D}(waiting for cycle data…)${R}\n"
    fi

    # ────────────────────────── GATE ──────────────────────────
    printf "\n${B}${MAG}  ⚡ GATE (last 5)${R}\n"
    printf "  ${D}──────────────────────────────────────────────────────────────────────────${R}\n"
    if [[ -n "$gates" ]]; then
        echo "$gates" | while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local ts pr sd tag verdict reason
            ts=$(echo "$line" | grep -o '[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}' | head -1)
            pr=$(echo "$line" | sed -n 's|.*V54 GATE \([^ ]*\).*|\1|p' | sed 's|/USDC:USDC||')
            sd=$(echo "$line" | sed -n 's/.*side=\([^ ]*\).*/\1/p')
            tag=$(echo "$line" | sed -n 's/.*tag=\([^ ]*\).*/\1/p')
            if echo "$line" | grep -q "ACCEPT"; then
                verdict="${BGGRN}${B} ACCEPT ${R}"
                reason=$(echo "$line" | sed -n 's/.*ACCEPT \(.*\)/\1/p')
                printf "  ${GRN}✓${R} ${D}%s${R} ${B}%-5s${R} %-5s %b  ${D}%s${R}\n" \
                    "$ts" "$pr" "$sd" "$verdict" "$reason"
            else
                verdict="${BGRED}${B} REJECT ${R}"
                reason=$(echo "$line" | sed -n 's/.*REJECT \(.*\)/\1/p')
                printf "  ${RED}✗${R} ${D}%s${R} ${B}%-5s${R} %-5s %b  ${RED}%s${R}\n" \
                    "$ts" "$pr" "$sd" "$verdict" "$reason"
            fi
        done
    else
        printf "  ${D}(no gate events yet)${R}\n"
    fi

    # ────────────────────────── TRADES / EXITS ──────────────────────────
    printf "\n${B}${BLU}  📊 TRADES / EXITS (last 5)${R}\n"
    printf "  ${D}──────────────────────────────────────────────────────────────────────────${R}\n"
    if [[ -n "$trades" ]]; then
        echo "$trades" | while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local ts
            ts=$(echo "$line" | grep -o '[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}' | head -1)
            if echo "$line" | grep -q "V54 LOSS"; then
                local pr pft rsn
                pr=$(echo "$line" | sed -n 's/.*V54 LOSS: \([^ ]*\).*/\1/p' | sed 's|/USDC:USDC||')
                pft=$(echo "$line" | sed -n 's/.*: [^ ]* \([+-]\?[0-9.]*\)%.*/\1/p')
                rsn=$(echo "$line" | sed -n 's/.*(\([^)]*\)).*/\1/p')
                printf "  ${RED}●${R} ${D}%s${R} ${B}%-5s${R}  ${RED}%s%%  %s${R}\n" "$ts" "$pr" "$pft" "$rsn"
            elif echo "$line" | grep -q "V54 COOLDOWN"; then
                local g until
                g=$(echo "$line" | sed -n 's/.*group \([A-Z]\).*/\1/p')
                until=$(echo "$line" | sed -n 's/.*until \(.*\)/\1/p')
                printf "  ${YLW}⏸${R} ${D}%s${R} group ${B}%s${R} cooldown until ${D}%s${R}\n" "$ts" "$g" "$until"
            elif echo "$line" | grep -q "profit_ratio"; then
                local pr pft rsn final
                pft=$(echo "$line" | sed -n "s/.*'profit_ratio': \([+-]\?[0-9.e-]*\).*/\1/p")
                rsn=$(echo "$line" | sed -n "s/.*'exit_reason': '\([^']*\)'.*/\1/p")
                pr=$(echo "$line" | sed -n "s/.*'base_currency': '\([^']*\)'.*/\1/p")
                final=$(echo "$line" | grep -o "'is_final_exit': True\|'is_final_exit': False")
                # Convert ratio to percent
                local pct
                pct=$(awk -v v="$pft" 'BEGIN{printf "%+.2f", v*100}')
                local c="${GRN}"; awk -v v="$pft" 'BEGIN{exit !(v<0)}' && c="${RED}"
                local fmark=""
                [[ "$final" == *"True"* ]] && fmark="${B}[final]${R}" || fmark="${D}[partial]${R}"
                printf "  %b●%b ${D}%s${R} ${B}%-5s${R}  %b%s%%${R}  ${D}%s${R} %b\n" \
                    "$c" "$R" "$ts" "${pr:-?}" "$c" "$pct" "${rsn:-?}" "$fmark"
            elif echo "$line" | grep -q "ADJUST_POS"; then
                local pr pft st ent
                pr=$(echo "$line" | sed -n 's/.*ADJUST_POS CALLED: \([^ ]*\).*/\1/p' | sed 's|/USDC:USDC||')
                pft=$(echo "$line" | sed -n 's/.*profit=\([+-]\?[0-9.]*\)%.*/\1/p')
                st=$(echo "$line" | sed -n 's/.*stake=\$\([0-9.]*\).*/\1/p')
                ent=$(echo "$line" | sed -n 's/.*entries=\([0-9]*\).*/\1/p')
                printf "  ${YLW}↑${R} ${D}%s${R} ${B}%-5s${R}  DCA chk profit=%s%% stake=\$%s entries=%s\n" \
                    "$ts" "$pr" "$pft" "$st" "$ent"
            else
                local short
                short=$(echo "$line" | sed 's/.* - //' | cut -c1-90)
                printf "  ${D}→ %s %s${R}\n" "$ts" "$short"
            fi
        done
    else
        printf "  ${D}(no closed trades yet)${R}\n"
    fi

    # ────────────────────────── LAST STAKE/LEV ──────────────────────────
    if [[ -n "$stake" || -n "$lev" ]]; then
        printf "\n${B}${CYN}  💵 LAST ENTRY PARAMS${R}\n"
        printf "  ${D}──────────────────────────────────────────────────────────────────────────${R}\n"
        if [[ -n "$stake" ]]; then
            local sv slv
            sv=$(echo "$stake" | sed -n 's/.*stake=\$\([0-9.]*\).*/\1/p')
            slv=$(echo "$stake" | sed -n 's/.*lev=\([0-9.]*\)x.*/\1/p')
            printf "  Stake: ${B}\$%s${R}   Leverage: ${B}%sx${R}\n" "$sv" "$slv"
        fi
        if [[ -n "$lev" ]]; then
            local lv prop maxlv
            lv=$(echo "$lev" | sed -n 's/.* lev=\([0-9.]*\)x.*/\1/p')
            prop=$(echo "$lev" | sed -n 's/.*proposed=\([0-9.]*\).*/\1/p')
            maxlv=$(echo "$lev" | sed -n 's/.*max=\([0-9.]*\).*/\1/p')
            printf "  Last LEV decision: ${B}%sx${R}  ${D}(proposed=%s, max=%s)${R}\n" "$lv" "$prop" "$maxlv"
        fi
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
