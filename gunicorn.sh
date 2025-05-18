#!/bin/bash
(set -a; source .env; set +a; gunicorn -b $HOST:$PORT -w 4 -k gevent "reddit_proxy:app" --access-logfile -)