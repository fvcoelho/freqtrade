#!/bin/bash
cd ~/freqtrade
source .venv/bin/activate

CONFIG="config_v53.json"
STRATEGY="ZScoreV53Strategy"
DB="user_data/v53_mainnet.sqlite"
LOG="user_data/logs/v53.log"

case "$1" in
    start)
        echo "Starting V53 MAINNET (real money)..."
        nohup freqtrade trade --strategy $STRATEGY --config $CONFIG --db-url sqlite:///$DB -v > $LOG 2>&1 &
        echo "Bot started. PID: $!"
        ;;
    stop)
        echo "Stopping bot..."
        pkill -f "freqtrade trade --strategy $STRATEGY"
        echo "Bot stopped."
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        if pgrep -f "freqtrade trade --strategy $STRATEGY" > /dev/null; then
            echo "V53 Warmup running"
            ps aux | grep freqtrade | grep -v grep | grep -v bot.sh
        else
            echo "Bot is stopped."
        fi
        ;;
    logs)
        tail -f $LOG 2>/dev/null || echo "No logs found"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        ;;
esac
