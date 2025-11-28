#!/usr/bin/env bash
set -euo pipefail

# Create and push this workspace to a new private GitHub repository using the GitHub CLI (gh).
# Requirements: https://cli.github.com/ (user authenticated with `gh auth login`)
# Usage: ./scripts/create_private_repo.sh <repo-name> [--org <org-name>] [--description "desc"]

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install it: https://cli.github.com/"
  exit 1
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <repo-name> [--org <org>] [--description \"desc\"]"
  exit 1
fi

REPO_NAME="$1"
shift

ORGANIZATION=""
DESCRIPTION="Private repo created from local workspace"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --org)
      ORGANIZATION="$2"
      shift 2
      ;;
    --description)
      DESCRIPTION="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Ensure we don't accidentally push secrets
if [ -f "accounts.json" ]; then
  echo "WARNING: accounts.json exists in this workspace. This file may contain secrets (passwords)."
  echo "Remove or move it before pushing, or confirm you know what you're doing."
  read -p "Continue and allow ignoring accounts.json (y/N)? " yn
  case "$yn" in
    [Yy]*) ;;
    *) echo "Aborting."; exit 1;;
  esac
fi

# Initialize git if needed
if [ ! -d .git ]; then
  git init
fi

git add .
git commit -m "chore: initial commit" || true

REMOTE_OPTS=(--private)
if [ -n "$ORGANIZATION" ]; then
  REMOTE_OPTS+=(--org "$ORGANIZATION")
fi

echo "Creating private repo '$REPO_NAME'..."
if [ -n "$ORGANIZATION" ]; then
  gh repo create "$ORGANIZATION/$REPO_NAME" --private --source=. --remote=origin --push --description "$DESCRIPTION"
else
  gh repo create "$REPO_NAME" --private --source=. --remote=origin --push --description "$DESCRIPTION"
fi

echo "Repository created and pushed to origin."
