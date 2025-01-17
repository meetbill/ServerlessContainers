#!/usr/bin/env bash
scriptDir=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
source "${scriptDir}/../../set_pythonpath.sh"

tmux new -d -s "Refeeder" "python3 src/Refeeder/Refeeder.py"
tmux new -d -s "DatabaseSnapshoter" "python3 src/Snapshoters/DatabaseSnapshoter.py"
tmux new -d -s "StructuresSnapshoter" "python3 src/Snapshoters/StructuresSnapshoter.py"

