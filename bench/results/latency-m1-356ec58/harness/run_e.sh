# P04c Part E runner. Usage: bash run_e.sh <E1|E2> <expected overlay GUID>
# Per run: overlay check -> machine gate -> one C1 run (no wrapper). STOP (exit 3) on any check failure.
set -u
PHASE="$1"; WANT="$2"
W=/d/sem_iitk/sem9/comp/_work/p04c
OUT=$W/e/out
cd "$W" || exit 2
source scripts/env.sh || exit 2
ORDER="1:old 1:new 2:new 2:old 3:old 3:new"
for item in $ORDER; do
  round=${item%%:*}; cond=${item##*:}; label="${PHASE}_r${round}_${cond}"
  ov=$(powershell.exe -NoProfile -Command "(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes').ActiveOverlayAcPowerScheme" | tr -d '\r')
  ac=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Battery).BatteryStatus" | tr -d '\r')
  api=$("$PY" -I scripts/overlay_api.py | tr -d '\r')
  echo "[$label] overlay_registry=$ov overlay_api=$api battery_status=$ac"
  if [ "$ov" != "$WANT" ] || [ "$api" != "$WANT" ]; then echo "STOP: overlay registry=$ov api=$api != $WANT"; exit 3; fi
  ov="$ov api=$api"
  g=$(powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:\sem_iitk\sem9\comp\_work\p04c\scripts\gate.ps1' | tr -d '\r')
  echo "$g" | sed "s/^/[$label] /"
  echo "$g" > "$OUT/${label}.gate.txt"; echo "overlay=$ov battery_status=$ac" >> "$OUT/${label}.gate.txt"
  if ! echo "$g" | grep -q "pass=True"; then echo "STOP: machine gate failed before $label"; exit 3; fi
  "$PY" -I scripts/c1_driver_p04c.py "D:/sem_iitk/sem9/comp/_work/p04c/e/$cond" plain \
      "D:/sem_iitk/sem9/comp/_work/p04c/e/out/${label}.json" "$label" > "$OUT/${label}.stdout.txt" 2>&1
  rc=$?
  echo "[$label] exit=$rc"; tail -1 "$OUT/${label}.stdout.txt"
  if [ $rc -ne 0 ]; then echo "CRASH in $label (reported; continuing per protocol: every run reported)"; fi
done
