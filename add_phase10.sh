#!/usr/bin/env bash
# Run from your ai-carryon-saas repo root, with
# phase10-monitoring-alerts.tar.gz already in this same directory.
#
# Usage: bash add_phase10.sh
set -e

echo "Current directory: $(pwd)"
git branch --show-current
echo "This should be your ai-carryon-saas repo root, on branch main, up to date."
sleep 2

if [ "$(git branch --show-current)" != "main" ]; then
  echo "ERROR: not on main. Run: git checkout main && git pull origin main"
  exit 1
fi

if [ ! -f phase10-monitoring-alerts.tar.gz ]; then
  echo "ERROR: phase10-monitoring-alerts.tar.gz not found in $(pwd)"
  echo "Move it here first, e.g.: mv ~/Downloads/phase10-monitoring-alerts.tar.gz ."
  exit 1
fi

git pull origin main

git checkout -b phase-10-monitoring-alerts

tar -xzf phase10-monitoring-alerts.tar.gz
rm phase10-monitoring-alerts.tar.gz

echo ""
echo "=== git status ==="
git status

echo ""
echo "Review the changes above, then press Enter to commit and push this new branch, or Ctrl+C to stop."
read -r _

git add -A
git commit -m "Phase 10: Health Agent + Alert Agent (Ch.18-19) — monitoring, retry-then-escalate, email + dashboard alerts"
git push origin phase-10-monitoring-alerts

echo ""
echo "Done. Now open this in your browser and merge the PR:"
echo "https://github.com/Unknown183-a/ai-carryon-saas/compare/main...phase-10-monitoring-alerts"
