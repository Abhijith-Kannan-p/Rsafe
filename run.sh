#!/usr/bin/env sh
# Usage: ./run.sh setup|dev|test|seed|screenshots|build
# Equivalent to `make <target>` for machines without make.
set -e
cmd="${1:-dev}"
case "$cmd" in
  setup|dev|test|seed|screenshots|build) npm run "$cmd" ;;
  *) echo "Unknown command: $cmd (use setup, dev, test, seed, screenshots, build)"; exit 1 ;;
esac
