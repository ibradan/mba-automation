#!/usr/bin/env bash
set -euo pipefail

# Manual steps to create a private GitHub repository (if you prefer the web UI), then push.
# Usage: ./scripts/manual_push.sh <git_remote_url>

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <git-remote-ssh-or-https-url>"
  exit 1
fi

REMOTE="$1"

if [ -f "accounts.json" ]; then
  echo "WARNING: accounts.json exists and may contain secrets. Consider moving or removing it before pushing."
  read -p "Continue? (y/N) " yn
  case "$yn" in
    [Yy]*) ;;
    *) echo "Aborting."; exit 1;;
  esac
fi

if [ ! -d .git ]; then
  git init
fi

git add .
git commit -m "chore: initial commit" || true
git remote add origin "$REMOTE" || true
git push -u origin main || git push -u origin master

echo "Push complete."
