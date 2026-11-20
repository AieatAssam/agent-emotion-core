#!/bin/sh
# usage: advance.sh ROUND HOURS [consolidate]   (orchestrator: move both forums and all agents forward)
R=$(cd "$(dirname "$0")" && pwd)
AC="python3 $R/run/install/agent-emotion-core/scripts/affect_core.py"
for c in control affect; do FORUM_FILE=$R/run/forum_$c.json python3 $R/forum.py round $1; done
for a in mara dov lin oz pia; do
  [ "$3" = consolidate ] && AFFECT_AGENT=$a AFFECT_STATE_DIR=$R/run/affect $AC consolidate --hours 0 >/dev/null
  AFFECT_AGENT=$a AFFECT_STATE_DIR=$R/run/affect $AC tick --hours $2
done
