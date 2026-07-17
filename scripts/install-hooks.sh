#!/bin/sh
# Active les hooks de protection des branches (règle R7 — README.md).
# À exécuter une fois après chaque clone : sh scripts/install-hooks.sh
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push 2>/dev/null || true
echo "✅ Hooks installés (core.hooksPath = .githooks)."
echo "   Vérification attendue : sur main ou develop, 'git commit' doit être REFUSÉ."
