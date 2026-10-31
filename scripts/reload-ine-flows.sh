#!/bin/sh
set -eu

usage() {
    cat <<'EOF'
Usage: reload-ine-flows.sh [--dry-run | --database]

Run all registered INE flows for every published period.
Default: preview database commands without network or database access.
--database executes sequential, transactional period replacements.
Empty results preserve stored data. Tables are never truncated.
Stops on the first failure; earlier periods may already be committed.
Set PYTHON to override the repository's .venv/bin/python interpreter.
EOF
}

mode=--dry-run
if [ "$#" -gt 1 ]; then
    usage >&2
    exit 2
fi
case "${1:---dry-run}" in
    --dry-run|--database) mode="${1:---dry-run}" ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
python=${PYTHON:-"$repo_root/.venv/bin/python"}
cd "$repo_root/flows-code"

flows=$("$python" - <<'PY'
import importlib
from pistadigital.cli.ine_flows import INDICATORS

for code, path in INDICATORS.items():
    module = importlib.import_module(path)
    period = "--all-years-months" if module.MONTHLY else "--all-years"
    print(f"{code}:{period}")
PY
)

if [ -z "$flows" ]; then
    echo "No registered INE flows found; refusing to report success." >&2
    exit 1
fi

if [ "$mode" = "--database" ]; then
    echo "Replacing all published INE periods. Empty results preserve stored data."
else
    echo "Preview only. Use --database to execute these replacements."
fi

for flow in $flows; do
    indicator=${flow%%:*}
    period=${flow#*:}
    printf '%s\n' "INE $indicator: $period --database"
    if [ "$mode" = "--database" ]; then
        if "$python" ine_flows.py --indicator "$indicator" "$period" --database; then
            printf 'Completed INE %s.\n' "$indicator"
        else
            status=$?
            printf 'INE %s failed (exit %s); stopping. Earlier periods may already be committed.\n' \
                "$indicator" "$status" >&2
            exit "$status"
        fi
    fi
done

if [ "$mode" = "--database" ]; then
    echo "All INE flows completed."
fi
