#!/bin/bash
cd /root/freqtrade
.venv/bin/freqtrade trade --config config_v53_dryrun.json --strategy ZScoreV53Strategy --db-url sqlite:///v53_dryrun.sqlite --logfile v53_dryrun.log
