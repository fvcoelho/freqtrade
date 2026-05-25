#!/bin/bash
cd ~/freqtrade
source .venv/bin/activate

CONFIG="config_v57_hyperliquid.json"
STRATEGY="ZScoreV57Strategy"
DB="user_data/v57_dryrun.sqlite"
LOG="user_data/logs/v57.log"

case "$1" in
    start)
        echo "Starting V57 (dry_run=true, Hyperliquid futures USDC)..."
        nohup freqtrade trade --strategy $STRATEGY --config $CONFIG --db-url sqlite:///$DB -v > $LOG 2>&1 &
        echo "Bot started. PID: $!"
        ;;
    stop)
        echo "Stopping V57 bot..."
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
            echo "V57 running"
            ps aux | grep freqtrade | grep -v grep | grep -v start_v57.sh
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
