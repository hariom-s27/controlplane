# source me: P04c process hygiene (names only, never values)
for v in $(env | sed -n 's/^\([^=]*\)=.*/\1/p' | grep -iE 'API_KEY|_TOKEN'); do echo "unset: $v"; unset "$v"; done
left=$(env | sed -n 's/^\([^=]*\)=.*/\1/p' | grep -iE 'API_KEY|_TOKEN')
if [ -n "$left" ]; then echo "ABORT: still set: $left"; return 1 2>/dev/null || exit 1; fi
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export TMP='D:\sem_iitk\sem9\comp\_work\p04c\tmp' TEMP='D:\sem_iitk\sem9\comp\_work\p04c\tmp'
export PY="/d/sem_iitk/sem9/comp/accenture/phase 2/controlplanestarter/controlplane/.venv/Scripts/python.exe"
echo "env ok: secrets-unset, HF offline, TMP=$TMP"
