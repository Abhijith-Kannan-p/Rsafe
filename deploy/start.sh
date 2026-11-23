#!/bin/sh
# Container entry point. Every start builds fresh synthetic data, so a restarted demo is clean.
set -e
cd /srv/backend

# Sign session cookies with a real secret. If the host did not provide one, make a random one
# for this run (sessions end when the container restarts, which also resets the data).
if [ -z "$RSAFE_SESSION_SECRET" ]; then
  RSAFE_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
  export RSAFE_SESSION_SECRET
  echo "RSAFE_SESSION_SECRET not set: using a random secret for this run."
fi

# Synthetic data only. Written to /tmp so the committed CSVs in the image are never touched.
python seed.py --out /tmp/rsafe-data

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
