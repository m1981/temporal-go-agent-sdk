#!/usr/bin/env bash
# truth-canary.sh v0.6.2 -- seeded-fault acceptance suite (seeded faults + TL hardening + adapter seam + bd normalization + ADR-002 work kernel + ADR-006 issue-fold hardening + INV-M dead-tripwire intake checks + ADR-005 impact verb + spec-health/doc-health incl. degradation paths + v0.6 solo-regime hardening: ADR-007 Q-faults, ADR-008 B-faults, ADR-009 E-faults, ADR-010 V-faults, ADR-011 H-faults, ADR-012 M1 + v0.6.2 review-finding faults: F1 arg-deny E5, F2 ts-evasion B3/B4, F3 scope-signal Q5/Q6).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PASS=0; FAIL=0
say()  { printf '%s\n' "$*"; }
ok()   { PASS=$((PASS+1)); say "  CAUGHT: $*"; }
miss() { FAIL=$((FAIL+1)); say "  MISSED: $*"; }

TMP1="$(mktemp -d)"; TMP2="$(mktemp -d)"; TMP3="$(mktemp -d)"
cleanup() { rm -rf "$TMP1" "$TMP2" "$TMP3"; }
trap cleanup EXIT

mkrepo() {
  cd "$1"
  git init -q -b main .
  git config user.email canary@truth.local
  git config user.name  truth-canary
  mkdir -p scripts .truth prompts
  touch .truth/claims.jsonl
  cp "$HERE/truth" scripts/truth
  cp "$HERE/../.truth/evidence-allow" .truth/evidence-allow
  cp "$HERE/check-truth.sh" scripts/check-truth.sh
  cp "$HERE/spec-health.sh" scripts/spec-health.sh
  cp "$HERE/doc-health.sh" scripts/doc-health.sh
  chmod +x scripts/truth scripts/check-truth.sh scripts/spec-health.sh scripts/doc-health.sh
}
T="python3 scripts/truth"
export TRUTH_ACTOR=canary TRUTH_SESSION=s-canary

# ======================================================= sandbox 1 (main)
mkrepo "$TMP1"
echo "hello" > watched.txt
echo "v1"    > fabricated.txt
printf 'verifier header\n---\nVERIFIER BODY\n\n1. RULE ONE.\n2. RULE TWO.\n' > prompts/truth-verifier.md
git add -A && git commit -qm "canary: init"

say "DOCTOR (G4): must FAIL on an unwired repo, PASS after wiring"
if $T doctor >/dev/null 2>&1; then
  miss "doctor passed a repo with no hooks, no gitattributes, no discovery"
else
  ok "doctor failed the unwired repo"
fi
echo ".truth/claims.jsonl merge=union" >> .gitattributes
printf '#!/usr/bin/env bash\nexec bash scripts/check-truth.sh\n' > .git/hooks/pre-commit
printf '#!/usr/bin/env bash\npython3 scripts/truth invalidate-scan --quiet\n' > .git/hooks/post-merge
chmod +x .git/hooks/pre-commit .git/hooks/post-merge
printf '# Agents\nTruth ledger: use scripts/truth (see .truth/README.md)\n' > AGENTS.md
git add -A && git commit -qm "canary: wire installation" --no-verify
if $T doctor >/dev/null 2>&1; then
  ok "doctor passed the wired repo"
else
  miss "doctor failed a correctly wired repo"; $T doctor || true
fi
# TL-1: hooks live where core.hooksPath says; .git/hooks wiring must not count
git config core.hooksPath .hookmgr/_
mkdir -p .hookmgr/_
if $T doctor >/dev/null 2>&1; then
  miss "doctor trusted .git/hooks while core.hooksPath points elsewhere"
else
  ok "doctor failed when core.hooksPath bypasses the wired hooks"
fi
# husky-style delegation: user hooks one level above the `_` shim dir, no +x
printf '#!/usr/bin/env sh\nbash scripts/check-truth.sh || exit 1\n' > .hookmgr/pre-commit
printf '#!/usr/bin/env sh\npython3 scripts/truth invalidate-scan --quiet\n' > .hookmgr/post-merge
if $T doctor >/dev/null 2>&1; then
  ok "doctor passed hook-manager wiring (hooksPath + _ delegation)"
else
  miss "doctor failed a correctly wired hook-manager repo"; $T doctor || true
fi
git config --unset core.hooksPath

say "FAULT B (INV-C): commit touching evidence paths must mark the claim stale"
CID_B=$($T claim "watched.txt says hello" --class VERIFIED \
        --evidence-cmd "cat watched.txt" --paths "watched.txt" --tier P0)
# ADR-010: agree verdicts come from a verifier session, never the author's
TRUTH_SESSION=s-canary-verifier $T verdict "$CID_B" agree --basis "canary: verified at filing" >/dev/null
git add .truth/claims.jsonl && git commit -qm "canary: claim B" --no-verify
echo "changed" >> watched.txt
git add watched.txt && git commit -qm "canary: mutate evidence" --no-verify
$T invalidate-scan --quiet
if $T list --stale --json | grep -q "$CID_B"; then
  ok "claim $CID_B stale after evidence path changed"
else
  miss "claim $CID_B still trusted after its evidence changed"
fi

say "FAULT C (T1): recheck must diverge when reality no longer matches"
CID_C=$($T claim "fabricated.txt says v1" --class VERIFIED \
        --evidence-cmd "cat fabricated.txt" --paths "fabricated.txt" --tier P1)
echo "v2" > fabricated.txt
if $T verdict "$CID_C" --recheck | grep -q diverge; then
  ok "recheck flagged hash mismatch on $CID_C"
else
  miss "recheck accepted stale evidence on $CID_C"
fi

say "FAULT O (TL-4): recheck with matching hash must report, not file"
echo hello > intact.txt
git add intact.txt   # INV-M (v0.5.4): a literal --paths entry must be tracked at filing time
CID_O=$($T claim "intact.txt says hello" --class VERIFIED \
        --evidence-cmd "cat intact.txt" --paths "intact.txt" --tier P1)
N_BEFORE=$(grep -c "" .truth/claims.jsonl)
$T verdict "$CID_O" --recheck >/dev/null
N_AFTER=$(grep -c "" .truth/claims.jsonl)
if [ "$N_AFTER" -eq "$N_BEFORE" ] && $T list --unverified | grep -q "$CID_O"; then
  ok "matching recheck filed nothing; $CID_O still awaits a judged verdict"
else
  miss "recheck auto-filed a verdict on matching evidence (verifier pre-committed)"
fi

say "FAULT P (TL-3): dispatch must self-describe integrity (rule count + prompt hash)"
DISPATCH=$($T dispatch "$CID_O")
STATED=$(printf '%s\n' "$DISPATCH" | sed -n 's/.*contains \([0-9][0-9]*\) numbered rules.*/\1/p' | head -1)
ACTUAL=$(printf '%s\n' "$DISPATCH" | grep -Ec '^[0-9]+\. ')
TERM_HASH=$(printf '%s\n' "$DISPATCH" | sed -n 's/^END-OF-DISPATCH sha256:\(.*\)$/\1/p')
FILE_HASH=$(python3 -c "import hashlib;print(hashlib.sha256(open('prompts/truth-verifier.md','rb').read()).hexdigest())")
if [ -n "$STATED" ] && [ "$STATED" -eq "$ACTUAL" ] && [ "$TERM_HASH" = "$FILE_HASH" ]; then
  ok "dispatch states $STATED rules (matches actual) and terminator hash matches prompt file"
else
  miss "dispatch self-description broken: stated=$STATED actual=$ACTUAL termhash=${TERM_HASH:-absent}"
fi

say "FAULT Q (TL-5): records must carry a real session id, never s-unknown"
TRUTH_SESSION="" $T claim "session fallback probe" --class UNVERIFIED --tier P2 >/dev/null
LAST_SESSION=$(tail -1 .truth/claims.jsonl | python3 -c "import json,sys;print(json.load(sys.stdin)['session'])")
if [ "$LAST_SESSION" != "s-unknown" ] && [ -n "$LAST_SESSION" ]; then
  ok "unset TRUTH_SESSION falls back to a derived id ($LAST_SESSION)"
else
  miss "record filed with session '$LAST_SESSION'"
fi
TRUTH_SESSION=s-custom-probe $T claim "session override probe" --class UNVERIFIED --tier P2 --duplicate-ok >/dev/null
if tail -1 .truth/claims.jsonl | grep -q '"session": "s-custom-probe"'; then
  ok "explicit TRUTH_SESSION is honored verbatim"
else
  miss "TRUTH_SESSION override not recorded"
fi

say "FAULT D (G10): claim past its ttl_days must expire to stale"
CID_D=$(TRUTH_NOW="2026-06-01T00:00:00+00:00" $T claim \
        "external API allows 100 req/min" --class INFERRED \
        --basis "vendor docs read 2026-06-01" --ttl-days 7 --tier P1)
$T invalidate-scan --quiet
if $T list --stale --json | grep -q "$CID_D"; then
  ok "claim $CID_D expired after ttl elapsed"
else
  miss "ttl_days is still a dead field: $CID_D outlived its ttl"
fi

say "FAULT G (G6): nondeterministic evidence command must be refused"
if $T claim "the clock ticks" --class VERIFIED \
     --evidence-cmd "date +%s%N" --paths "watched.txt" --tier P2 2>/dev/null; then
  miss "intake accepted nondeterministic evidence"
else
  ok "intake refused nondeterministic evidence"
fi

say "FAULT Q1 (ADR-007): universal claim text over a scoped command must be refused"
if $T claim "no occurrences remain anywhere in the codebase" --class VERIFIED \
     --evidence-cmd "grep -rc hello --include=watched.txt ." --paths "watched.txt" \
     --tier P1 2>/dev/null; then
  miss "intake accepted a universal quantifier over an --include-scoped command"
else
  ok "quantifier-scope mismatch refused (the pilot's dominant failure shape)"
fi
say "FAULT Q2 (ADR-007): --scope-ok with a sentence must file and store scope_basis"
if CID_Q2=$($T claim "no occurrences remain anywhere in the codebase" --class VERIFIED \
     --evidence-cmd "grep -rc hello --include=watched.txt ." --paths "watched.txt" \
     --tier P1 --scope-ok "the quantifier is deliberately checked via the include filter" 2>/dev/null) \
   && tail -1 .truth/claims.jsonl | grep -q '"scope_basis"'; then
  ok "override filed with an auditable scope_basis ($CID_Q2)"
else
  miss "--scope-ok override failed or scope_basis absent from the record"
fi
say "FAULT Q3 (ADR-007): scoped text with no quantifier must pass silently"
if $T claim "watched.txt mentions hello at least once" --class VERIFIED \
     --evidence-cmd "grep -c hello --include=watched.txt -r ." --paths "watched.txt" \
     --tier P2 --duplicate-ok >/dev/null 2>&1; then
  ok "non-universal claim over a scoped command passed"
else
  miss "gate misfired on a claim with no universal quantifier"
fi
say "FAULT Q4 (ADR-007): universal text over an unscoped command must pass silently"
if $T claim "watched.txt never went missing" --class VERIFIED \
     --evidence-cmd "cat watched.txt" --paths "watched.txt" \
     --tier P2 --duplicate-ok >/dev/null 2>&1; then
  ok "universal claim over an unscoped command passed (no S signal)"
else
  miss "gate misfired with no scoping signal in the command"
fi
say "FAULT Q5 (ADR-007, F3): a ripgrep -t type filter is a scope signal (no slash)"
if $T claim "no occurrences remain anywhere in the codebase" --class VERIFIED \
     --evidence-cmd "grep -t txt -rc hello ." --paths "watched.txt" \
     --tier P1 2>/dev/null; then
  miss "intake accepted a universal quantifier over a -t-scoped command (F3 evasion)"
else
  ok "-t type-filter scope signal caught under a universal quantifier"
fi
say "FAULT Q6 (ADR-007, F3): a glob-metacharacter positional is a scope signal"
if $T claim "X appears everywhere in the code" --class VERIFIED \
     --evidence-cmd "grep -c hello watched.*" --paths "watched.txt" \
     --tier P1 2>/dev/null; then
  miss "intake accepted a universal quantifier over a glob-scoped command (F3 evasion)"
else
  ok "glob-metacharacter positional scope signal caught under a universal quantifier"
fi

say "FAULT E1 (ADR-009): a non-allowlisted program in the evidence command must be refused"
if $T claim "the network is reachable" --class VERIFIED \
     --evidence-cmd "curl -s https://example.com" --ttl-days 7 --tier P1 2>/dev/null; then
  miss "intake accepted an unscreened program (deferred execution channel open)"
else
  ok "unlisted program refused at intake"
fi
say "FAULT E2 (ADR-009): a pipeline of allowlisted programs must pass"
if CID_E2=$($T claim "watched.txt is a multi-word file" --class VERIFIED \
     --evidence-cmd "cat watched.txt | wc -w" --paths "watched.txt" \
     --tier P2 --duplicate-ok 2>/dev/null); then
  ok "allowlisted pipeline accepted ($CID_E2)"
else
  miss "screen wrongly refused a read-only allowlisted pipeline"
fi
say "FAULT E3 (ADR-009): recheck must refuse to execute an unscreened command"
CID_E3=$($T claim "unsafe evidence probe" --class VERIFIED \
     --evidence-cmd "python3 -c 'print(1)'" --paths "watched.txt" \
     --tier P2 --evidence-unsafe-ok --duplicate-ok 2>/dev/null)
N_E3=$(grep -c "" .truth/claims.jsonl)
if [ -z "$CID_E3" ]; then
  miss "fault injection failed: --evidence-unsafe-ok claim was never filed"
elif $T verdict "$CID_E3" --recheck >/dev/null 2>&1; then
  miss "recheck EXECUTED an unscreened evidence command (the ADR-009 channel)"
else
  N_E3_AFTER=$(grep -c "" .truth/claims.jsonl)
  if [ "$N_E3_AFTER" -eq "$N_E3" ]; then
    ok "recheck declined the unscreened command and filed nothing"
  else
    miss "recheck declined but still filed $((N_E3_AFTER-N_E3)) record(s)"
  fi
fi
say "FAULT E4 (ADR-009): a missing allowlist must fail VERIFIED intake closed"
mv .truth/evidence-allow evidence-allow.e4.bak
if $T claim "screen machinery absent" --class VERIFIED \
     --evidence-cmd "cat watched.txt" --paths "watched.txt" \
     --tier P2 --duplicate-ok >/dev/null 2>&1; then
  miss "VERIFIED intake proceeded with no allowlist (screen failed open)"
else
  ok "missing allowlist failed closed with guidance"
fi
mv evidence-allow.e4.bak .truth/evidence-allow
say "FAULT E5 (ADR-009, F1): an allowlisted program's exec/write flag must be refused"
echo "sort" >> .truth/evidence-allow  # ensure the program is allowlisted
if $T claim "the log is sorted into place" --class VERIFIED \
     --evidence-cmd "sort -o /tmp/pwn watched.txt" --paths "watched.txt" \
     --tier P2 --duplicate-ok >/dev/null 2>&1; then
  miss "screen accepted 'sort -o' -- an allowlisted program's file-write flag (F1 channel)"
else
  ok "allowlisted program's exec/write flag refused (sort -o)"
fi

say "FAULT T (INV-M): a dead evidence-path tripwire must be refused at intake"
if $T claim "a and watched are fine" --class VERIFIED \
     --evidence-cmd "cat watched.txt" --paths "watched.txt fabricated.txt" \
     --tier P1 2>/dev/null; then
  miss "intake accepted a space-joined literal (comma forgotten) -- dead tripwire on arrival"
else
  ok "intake refused the whitespace-no-comma literal"
fi
if $T claim "ghost.sh is fine" --class VERIFIED \
     --evidence-cmd "echo ok" --paths "ghost.sh" --tier P1 2>/dev/null; then
  miss "intake accepted a literal matching zero tracked files"
else
  ok "intake refused the zero-match literal"
fi
if CID_T=$($T claim "watched and fabricated are fine" --class VERIFIED \
     --evidence-cmd "cat watched.txt fabricated.txt" \
     --paths "watched.txt,fabricated.txt" --tier P1 --duplicate-ok 2>/dev/null); then
  ok "comma-separated literals still accepted ($CID_T)"
else
  miss "intake wrongly refused legitimate comma-separated paths"
fi
if $T claim "future docs stay clean" --class VERIFIED \
     --evidence-cmd "echo ok" --paths "ghost-dir/*.md" --tier P1 --duplicate-ok >/dev/null 2>&1; then
  ok "explicit glob matching nothing yet is exempt (legitimate intent)"
else
  miss "intake wrongly refused an explicit glob with zero current matches"
fi

say "FAULT H (G12): a verdict after retraction must not resurrect the claim"
CID_H=$($T claim "this claim is simply wrong" --tier P2)
# ADR-011: headless human retraction acknowledges the exact id
TRUTH_HUMAN=1 TRUTH_HUMAN_ACK="$CID_H" $T verdict "$CID_H" retracted --basis "human: factually wrong, tombstoned" >/dev/null
if $T verdict "$CID_H" agree --basis "resurrection attempt" >/dev/null 2>&1; then
  miss "tool accepted a verdict on a retracted claim"
else
  ok "tool refused a verdict on retracted $CID_H"
fi
if $T list --retracted --json | grep -q "$CID_H" && \
   ! $T list --live --json | grep -q "$CID_H"; then
  ok "fold holds $CID_H as retracted (terminal)"
else
  miss "retracted claim $CID_H changed status"
fi

say "FAULT I (G8): near-duplicate of an active claim must be refused"
$T claim "the payments module handles all currency conversion logic" --tier P2 >/dev/null
if $T claim "the payments module handles currency conversion" --tier P2 2>/dev/null; then
  miss "intake accepted a near-duplicate active claim"
else
  ok "intake refused the near-duplicate"
fi
if DUP=$($T claim "the payments module handles currency conversion" \
         --tier P2 --duplicate-ok 2>/dev/null); then
  ok "--duplicate-ok override works ($DUP)"
else
  miss "--duplicate-ok override rejected a legitimate refile"
fi
# MEDIUM-1: the override must leave an auditable trace, not vanish silently
if python3 -c "import json,sys
for line in open('.truth/claims.jsonl'):
    r=json.loads(line)
    if r.get('id')=='$DUP':
        sys.exit(0 if r['payload'].get('overridden_duplicates') else 1)
sys.exit(1)" 2>/dev/null; then
  ok "the --duplicate-ok record carries overridden_duplicates (MEDIUM-1 trace)"
else
  miss "the --duplicate-ok override left no overridden_duplicates trace"
fi

say "FAULT J (ADR-001): issue premised on a stale claim must be HELD"
cat > bd <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "ready" ]; then
  echo '[{"id":"bd-x1","title":"issue on stale premise"},{"id":"bd-x2","title":"issue on live premise"}]'
fi
EOF
chmod +x bd
CID_L=$($T claim "watched.txt now says hello changed" --class VERIFIED \
        --evidence-cmd "cat watched.txt" --paths "watched.txt" --tier P1 --duplicate-ok)
TRUTH_SESSION=s-canary-verifier $T verdict "$CID_L" agree --basis "canary: verified at filing" >/dev/null
$T premise bd-x1 "$CID_B" >/dev/null
$T premise bd-x2 "$CID_L" >/dev/null
READY_OUT=$(PATH="$PWD:$PATH" $T ready)
if echo "$READY_OUT" | grep -q "^HELD bd-x1" && echo "$READY_OUT" | grep -q "^bd-x2"; then
  ok "bd-x1 held on stale premise; bd-x2 passed on live premise"
else
  miss "ready join wrong: $READY_OUT"
fi
# v0.4.1 -- the adapter seam is a property, not a promise:
READY_ENV=$(PATH="/usr/bin:/bin" TRUTH_TRACKER_CMD="$PWD/bd ready --json" $T ready)
if echo "$READY_ENV" | grep -q "^HELD bd-x1" && echo "$READY_ENV" | grep -q "^bd-x2"; then
  ok "TRUTH_TRACKER_CMD adapter joins identically (no bd on PATH)"
else
  miss "TRUTH_TRACKER_CMD adapter wrong: $READY_ENV"
fi
READY_STDIN=$(./bd ready | $T ready --stdin)
if echo "$READY_STDIN" | grep -q "^HELD bd-x1" && echo "$READY_STDIN" | grep -q "^bd-x2"; then
  ok "--stdin adapter joins identically (tracker-agnostic pipe)"
else
  miss "--stdin adapter wrong: $READY_STDIN"
fi
# v0.4.1 -- the bundled bd adapter must normalize varied JSON shapes and
# still drive the join (restored after TL merge dropped these two checks).
cat > bd-variant <<'EOF'
#!/usr/bin/env bash
printf '%s' '{"issues":[{"issue_id":"bd-x1","summary":"issue on stale premise"},{"key":"bd-x2","name":"issue on live premise"}]}'
EOF
chmod +x bd-variant
READY_ADAPT=$(TRUTH_BD_CMD="$PWD/bd-variant" TRUTH_TRACKER_CMD="bash $HERE/truth-bd-adapter.sh" $T ready)
if echo "$READY_ADAPT" | grep -q "^HELD bd-x1" && echo "$READY_ADAPT" | grep -q "^bd-x2"; then
  ok "bd adapter normalizes {issue_id,summary,key,name} and joins correctly"
else
  miss "bd adapter join wrong: $READY_ADAPT"
fi
# adapter must FAIL LOUDLY (non-zero) rather than emit an empty join
cat > bd-noid <<'EOF'
#!/usr/bin/env bash
printf '%s' '[{"foo":"bar"}]'
EOF
chmod +x bd-noid
if TRUTH_BD_CMD="$PWD/bd-noid" bash "$HERE/truth-bd-adapter.sh" >/dev/null 2>&1; then
  miss "bd adapter silently accepted issues with no id"
else
  ok "bd adapter fails loudly when no id field is recognized"
fi
if PATH="/usr/bin:/bin" TRUTH_TRACKER_CMD="definitely-not-a-tracker --json" $T ready >/dev/null 2>&1; then
  miss "ready succeeded with a nonexistent tracker command"
else
  if PATH="/usr/bin:/bin" TRUTH_TRACKER_CMD="definitely-not-a-tracker --json" $T ready 2>&1 | grep -q "Traceback"; then
    miss "missing tracker produced a raw traceback, not guidance"
  else
    ok "missing tracker degrades with guidance, no traceback"
  fi
fi

# ---- FAULT K (v0.4): duplicate-id append must not resurrect a tombstone ----
say "FAULT K (INV-G'): appending a duplicate claim id must not reset status"
python3 - "$CID_H" <<'PYEOF'
import json, sys
rec={"id":sys.argv[1],"kind":"claim","actor":"agent-x","session":"s-evil",
     "ts":"2099-01-01T00:00:00+00:00",
     "payload":{"text":"resurrection via duplicate id","evidence_class":"UNVERIFIED",
                "cost_tier":"P0","ttl_days":None,"evidence_paths":[]}}
open(".truth/claims.jsonl","a").write(json.dumps(rec,sort_keys=True)+"\n")
PYEOF
if $T list --retracted --json | grep -q "$CID_H" && \
   ! $T list --unverified --json | grep -q "$CID_H"; then
  ok "duplicate-id append ignored; $CID_H stays retracted"
else
  miss "duplicate-id append resurrected retracted $CID_H"
fi

say "FAULT B1 (ADR-008): a BACKDATED duplicate-id append must fail validate (commit gate blocks)"
cp .truth/claims.jsonl claims.b1.bak
python3 - "$CID_H" <<'PYEOF'
import json, sys
rec={"id":sys.argv[1],"kind":"claim","actor":"agent-x","session":"s-evil",
     "ts":"2000-01-01T00:00:00+00:00",
     "payload":{"text":"content substitution via backdated duplicate","evidence_class":"UNVERIFIED",
                "cost_tier":"P0","ttl_days":None,"evidence_paths":[]}}
open(".truth/claims.jsonl","a").write(json.dumps(rec,sort_keys=True)+"\n")
PYEOF
if ! grep -q "content substitution via backdated" .truth/claims.jsonl; then
  miss "fault injection failed: backdated duplicate was never appended"
elif $T validate >/dev/null 2>&1; then
  miss "validate passed a backdated duplicate id (canonical-order substitution open)"
else
  ok "validate failed the backdated duplicate; the commit gate now blocks INV-G's composition gap"
fi
mv claims.b1.bak .truth/claims.jsonl

say "FAULT B2 (ADR-008): an IDENTICAL duplicated line (union-merge shape) must still validate"
cp .truth/claims.jsonl claims.b2.bak
tail -1 .truth/claims.jsonl >> .truth/claims.jsonl
if $T validate >/dev/null 2>&1; then
  ok "identical duplicate line (equal ts) passed -- legitimate union-merge shape"
else
  miss "validate rejected a union-merge-duplicated identical line"
fi
mv claims.b2.bak .truth/claims.jsonl

say "FAULT B3 (ADR-008, F2): a backdated duplicate with a tz-NAIVE ts must fail validate"
cp .truth/claims.jsonl claims.b3.bak
python3 - "$CID_H" <<'PYEOF'
import json, sys
# naive ts (no offset) string-sorts before the tz-aware genuine record;
# the pre-F2 parsed comparison abstained on the tz mismatch and passed it
rec={"id":sys.argv[1],"kind":"claim","actor":"agent-x","session":"s-evil",
     "ts":"2026-01-01T00:00:00",
     "payload":{"text":"substitution via naive-ts backdated duplicate","evidence_class":"UNVERIFIED",
                "cost_tier":"P0","ttl_days":None,"evidence_paths":[]}}
open(".truth/claims.jsonl","a").write(json.dumps(rec,sort_keys=True)+"\n")
PYEOF
if ! grep -q "naive-ts backdated" .truth/claims.jsonl; then
  miss "fault injection failed: naive-ts duplicate was never appended"
elif $T validate >/dev/null 2>&1; then
  miss "validate passed a naive-ts backdated duplicate (F2 evasion still open)"
else
  ok "validate failed the naive-ts backdated duplicate (F2 closed)"
fi
mv claims.b3.bak .truth/claims.jsonl

say "FAULT B4 (ADR-008, F2): a backdated duplicate with an UNPARSEABLE ts must fail validate"
cp .truth/claims.jsonl claims.b4.bak
python3 - "$CID_H" <<'PYEOF'
import json, sys
# junk ts made parse_ts return None, so the pre-F2 comparison abstained;
# by raw string it still sorts before any ISO ts and wins the fold
rec={"id":sys.argv[1],"kind":"claim","actor":"agent-x","session":"s-evil",
     "ts":"1",
     "payload":{"text":"substitution via junk-ts backdated duplicate","evidence_class":"UNVERIFIED",
                "cost_tier":"P0","ttl_days":None,"evidence_paths":[]}}
open(".truth/claims.jsonl","a").write(json.dumps(rec,sort_keys=True)+"\n")
PYEOF
if ! grep -q "junk-ts backdated" .truth/claims.jsonl; then
  miss "fault injection failed: junk-ts duplicate was never appended"
elif $T validate >/dev/null 2>&1; then
  miss "validate passed a junk-ts backdated duplicate (F2 evasion still open)"
else
  ok "validate failed the junk-ts backdated duplicate (F2 closed)"
fi
mv claims.b4.bak .truth/claims.jsonl

# ---- FAULT L (v0.4): re-verification must survive the next scan ----------
say "FAULT L: re-verified claim must stay live across a subsequent scan"
CID_R=$($T claim "watched.txt has multiple lines" --class VERIFIED \
        --evidence-cmd "wc -l < watched.txt" --paths "watched.txt" --tier P1 --duplicate-ok)
echo "another line" >> watched.txt
git add watched.txt && git commit -qm "canary: touch evidence again" --no-verify
$T invalidate-scan --quiet
TRUTH_SESSION=s-canary-verifier $T verdict "$CID_R" agree --basis "human re-verified at new HEAD" >/dev/null
$T invalidate-scan --quiet
if $T list --live --json | grep -q "$CID_R"; then
  ok "re-verified $CID_R stayed live (anchor advanced)"
else
  miss "re-verified $CID_R re-staled on the frozen anchor"
fi

# ---- FAULT M (v0.4) + H1-H3 (ADR-011): tombstone confirmation ladder ------
say "FAULT M (G12 enforced): retraction without TRUTH_HUMAN=1 must be refused"
CID_M=$($T claim "a claim a verifier wants dead" --tier P2)
if $T verdict "$CID_M" retracted --basis "verifier overreach" >/dev/null 2>&1; then
  miss "non-human retraction accepted"
else
  ok "retraction refused without TRUTH_HUMAN=1"
fi
say "FAULT H1 (ADR-011): TRUTH_HUMAN=1 alone, headless, must be refused"
if TRUTH_HUMAN=1 $T verdict "$CID_M" retracted --basis "agent set the env var" >/dev/null 2>&1; then
  miss "env-var-only retraction accepted with no TTY and no acknowledgment"
else
  ok "headless TRUTH_HUMAN=1 without acknowledgment refused"
fi
say "FAULT H3 (ADR-011): an acknowledgment naming a different id must be refused"
if TRUTH_HUMAN=1 TRUTH_HUMAN_ACK="tr-deadbeef" $T verdict "$CID_M" retracted --basis "stale ack" >/dev/null 2>&1; then
  miss "retraction accepted under an acknowledgment naming another id"
else
  ok "mismatched TRUTH_HUMAN_ACK refused (lingering exports cannot kill arbitrary claims)"
fi
say "FAULT H2 (ADR-011): id-specific acknowledgment must be accepted"
if TRUTH_HUMAN=1 TRUTH_HUMAN_ACK="$CID_M" $T verdict "$CID_M" retracted --basis "human confirms" >/dev/null 2>&1; then
  ok "human-confirmed retraction accepted (exact-id acknowledgment)"
else
  miss "human-confirmed retraction refused"
fi

say "FAULT V1 (ADR-010): agree from the claim's own session must be refused"
CID_V=$($T claim "self-verification probe" --tier P2)
if $T verdict "$CID_V" agree --basis "I checked my own work" >/dev/null 2>&1; then
  miss "the authoring session filed its own agree (self-verification open)"
else
  ok "same-session agree refused; dispatch to a fresh session required"
fi
say "FAULT V3 (ADR-010): diverge from the claim's own session must be ALLOWED (self-incrimination)"
if $T verdict "$CID_V" diverge --basis "author retracts confidence: probe was wrong" >/dev/null 2>&1; then
  ok "same-session diverge accepted (runs against interest)"
else
  miss "self-incrimination was refused -- corrections must stay cheap"
fi
say "FAULT V2 (ADR-010): agree from a different session must be accepted"
CID_V2=$($T claim "independent verification probe" --tier P2)
if TRUTH_SESSION=s-canary-verifier $T verdict "$CID_V2" agree --basis "independently decoded and confirmed" >/dev/null 2>&1; then
  ok "fresh-session agree accepted"
else
  miss "the verifier path itself is broken"
fi

say "FAULT M1 (ADR-012): diverge --mechanical must round-trip subtype to the queue"
CID_M1=$($T claim "recipe-drift probe" --tier P1)
TRUTH_SESSION=s-canary-verifier $T verdict "$CID_M1" diverge --mechanical --basis "output format changed, fact holds" >/dev/null
if $T queue --json | grep -q "mechanical" && \
   $T stats --json | grep -q '"diverge_mechanical": 1'; then
  ok "mechanical subtype visible in queue and split out in stats"
else
  miss "mechanical divergence subtype lost between verdict, queue, and stats"
fi

# ---- FAULT R (ADR-002, v0.5): native work kernel ---------------------------
say "FAULT R (ADR-002): premise-at-birth must warn when skipped"
WK_NP=$($T issue "kernel probe with no premise" 2>r_warn.txt)
if grep -q "premise-at-birth" r_warn.txt && [ -n "$WK_NP" ]; then
  ok "issue filed without premises carries the discipline warning ($WK_NP)"
else
  miss "no premise-at-birth warning: $(cat r_warn.txt)"
fi
rm -f r_warn.txt

say "FAULT R2 (ADR-002): unknown dep must be rejected at filing (cycle defense)"
if $T issue "dep on nothing" --deps wk-deadbeef >/dev/null 2>&1; then
  miss "issue accepted a dep on a nonexistent wk- id"
else
  ok "unknown dep refused -- CLI dep graphs stay acyclic by construction"
fi

say "FAULT R3 (ADR-002): native ready must HOLD broken premises, pass live ones"
WK_LIVE=$($T issue "kernel issue on live premise" --premise "$CID_R" 2>/dev/null)
WK_STALE=$($T issue "kernel issue on stale premise" --premise "$CID_B" 2>/dev/null)
READY_NATIVE=$(PATH="/usr/bin:/bin" $T ready)
if echo "$READY_NATIVE" | grep -q "^$WK_LIVE" && \
   echo "$READY_NATIVE" | grep -q "^HELD $WK_STALE"; then
  ok "native ready: $WK_LIVE passes, $WK_STALE HELD (no tracker involved)"
else
  miss "native ready join wrong: $READY_NATIVE"
fi

say "FAULT R4 (ADR-002): dep-blocked issue must be absent until its dep closes"
WK_DEP=$($T issue "kernel issue blocked by dep" --deps "$WK_LIVE" 2>/dev/null)
if PATH="/usr/bin:/bin" $T ready | grep -q "^$WK_DEP"; then
  miss "dep-blocked $WK_DEP appeared in ready"
else
  ok "dep-blocked $WK_DEP absent from ready"
fi
$T start "$WK_LIVE" >/dev/null
$T done "$WK_LIVE" --basis "canary: dep work finished" >/dev/null
if PATH="/usr/bin:/bin" $T ready | grep -q "^$WK_DEP"; then
  ok "$WK_DEP became ready after its dep closed"
else
  miss "$WK_DEP still blocked after dep closed"
fi

say "FAULT R5 (ADR-002): kernel-as-tracker seam must join identically to native"
NATIVE_OUT=$(PATH="/usr/bin:/bin" $T ready)
SEAM_OUT=$($T issues --ready-json | $T ready --stdin)
if [ "$NATIVE_OUT" = "$SEAM_OUT" ] && [ -n "$NATIVE_OUT" ]; then
  ok "issues --ready-json | ready --stdin equals native ready (seam == kernel)"
else
  miss "seam and kernel disagree: native=[$NATIVE_OUT] seam=[$SEAM_OUT]"
fi

say "FAULT R6 (ADR-002/G12): cancel is a human tombstone; terminal after"
WK_DEAD=$($T issue "kernel issue a verifier wants dead" 2>/dev/null)
if $T done "$WK_DEAD" --cancel --basis "agent overreach" >/dev/null 2>&1; then
  miss "non-human cancel accepted"
else
  ok "cancel refused without TRUTH_HUMAN=1"
fi
if TRUTH_HUMAN=1 $T done "$WK_DEAD" --cancel --basis "env var alone" >/dev/null 2>&1; then
  miss "env-var-only cancel accepted headless (ADR-011)"
else
  ok "headless TRUTH_HUMAN=1 cancel without acknowledgment refused (ADR-011)"
fi
if TRUTH_HUMAN=1 TRUTH_HUMAN_ACK="$WK_DEAD" $T done "$WK_DEAD" --cancel --basis "human confirms" >/dev/null 2>&1; then
  ok "human-confirmed cancel accepted (exact-id acknowledgment)"
else
  miss "human-confirmed cancel refused"
fi
if $T done "$WK_DEAD" --reopen --basis "resurrection attempt" >/dev/null 2>&1 || \
   $T start "$WK_DEAD" >/dev/null 2>&1; then
  miss "cancelled $WK_DEAD accepted a lifecycle event (not terminal)"
else
  ok "cancelled $WK_DEAD is terminal: reopen and start both refused"
fi

say "FAULT R7 (ADR-002): done --claim must file both records or neither"
WK_AT=$($T issue "kernel issue closing with a claim" 2>/dev/null)
N_BEFORE=$(grep -c "" .truth/claims.jsonl)
if $T done "$WK_AT" --basis "canary" --claim "the clock ticked" \
     --class VERIFIED --evidence-cmd "date +%s%N" --paths "watched.txt" \
     2>/dev/null; then
  miss "done --claim accepted nondeterministic completion evidence"
else
  N_AFTER=$(grep -c "" .truth/claims.jsonl)
  if [ "$N_AFTER" -eq "$N_BEFORE" ]; then
    ok "failed claim intake filed NEITHER record (issue still open)"
  else
    miss "failed claim intake left a torn write ($((N_AFTER-N_BEFORE)) record(s))"
  fi
fi
DONE_OUT=$($T done "$WK_AT" --basis "canary: finished" \
           --claim "intact.txt still says hello after kernel work" \
           --class VERIFIED --evidence-cmd "cat intact.txt" \
           --paths "intact.txt" --duplicate-ok)
N_FINAL=$(grep -c "" .truth/claims.jsonl)
if [ "$N_FINAL" -eq $((N_BEFORE + 2)) ] && echo "$DONE_OUT" | grep -q "filed tr-" \
   && $T issues --json | grep -A1 "\"id\": \"$WK_AT\"" | grep -q closed; then
  ok "claim-at-death filed claim + closed event atomically"
else
  miss "claim-at-death wrong: lines $N_BEFORE->$N_FINAL, out=$DONE_OUT"
fi

say "FAULT R8 (INV-A): mutating a historical issue record must block the commit"
git add -A && git commit -qm "canary: settle kernel records" --no-verify
python3 - "$WK_LIVE" <<'PYEOF'
import sys
lines = open(".truth/claims.jsonl").readlines()
for i, ln in enumerate(lines):
    if f'"id": "{sys.argv[1]}"' in ln and '"kind": "issue"' in ln:
        lines[i] = ln.replace('"kind": "issue"', '"kind": "ISSUE_TAMPERED"')
        break
open(".truth/claims.jsonl", "w").writelines(lines)
PYEOF
git add .truth/claims.jsonl
if ! grep -q ISSUE_TAMPERED .truth/claims.jsonl; then
  miss "fault injection failed: issue record was never mutated"
elif bash scripts/check-truth.sh >/dev/null 2>&1; then
  miss "gate accepted a mutated historical issue record"
else
  ok "gate blocked the tampered issue record"
fi
git checkout -q -- .truth/claims.jsonl

say "FAULT R9 (ADR-006): appending a duplicate issue id must not strip premises"
python3 - "$WK_STALE" <<'PYEOF'
import json, sys
wid = sys.argv[1]
rec = {"id": wid, "kind": "issue", "actor": "agent-x", "session": "s-evil",
       "ts": "2099-01-01T00:00:00+00:00",
       "payload": {"title": "kernel issue on stale premise", "text": "",
                   "deps": [], "premises": []}}
open(".truth/claims.jsonl", "a").write(json.dumps(rec, sort_keys=True) + "\n")
PYEOF
if ! grep -q '"session": "s-evil"' .truth/claims.jsonl; then
  miss "fault injection failed: duplicate issue record was never appended"
elif PY3="$(command -v python3)" && PATH="/usr/bin:/bin" "$PY3" scripts/truth ready | grep -q "^HELD $WK_STALE"; then
  ok "duplicate-id append ignored; $WK_STALE still HELD (premises intact)"
else
  miss "duplicate-id append stripped $WK_STALE's premises -- it is now ready"
fi
git checkout -q -- .truth/claims.jsonl 2>/dev/null || true

say "FAULT W1 (ADR-005): impact on a watched path must report the claim and exit 3"
echo whisper > w.txt
git add w.txt   # INV-M: literal paths must be tracked at filing
CID_W=$($T claim "w.txt says whisper" --class VERIFIED \
        --evidence-cmd "cat w.txt" --paths "w.txt" --tier P0 --duplicate-ok)
W1_OUT=$($T impact w.txt) && W1_RC=0 || W1_RC=$?
if ! grep -q "$CID_W" .truth/claims.jsonl; then
  miss "fault injection failed: watched claim $CID_W was never filed"
elif [ "$W1_RC" -eq 3 ] && echo "$W1_OUT" | grep -q "STALES $CID_W"; then
  ok "impact predicted STALES $CID_W and exited 3"
else
  miss "impact on watched path wrong (rc=$W1_RC): $W1_OUT"
fi

say "FAULT W2 (ADR-005): impact on an unwatched path must stay silent and exit 0 (fatigue budget)"
echo quiet > unwatched-w2.txt
git add unwatched-w2.txt
W2_OUT=$($T impact unwatched-w2.txt) && W2_RC=0 || W2_RC=$?
if [ "$W2_RC" -eq 0 ] && [ -z "$W2_OUT" ]; then
  ok "unwatched path produced zero output, exit 0"
else
  miss "impact broke the fatigue budget (rc=$W2_RC): '$W2_OUT'"
fi

say "FAULT W3 (ADR-005): impact must predict which work ready would HOLD"
WK_W=$($T issue "work standing on w.txt" --premise "$CID_W" 2>/dev/null)
W3_OUT=$($T impact w.txt) && W3_RC=0 || W3_RC=$?
if ! $T issues --json | grep -q "$WK_W"; then
  miss "fault injection failed: issue $WK_W was never filed"
elif [ "$W3_RC" -eq 3 ] && echo "$W3_OUT" | grep -q "HOLDs.*$WK_W"; then
  ok "impact predicted ready HOLDs $WK_W"
else
  miss "impact missed the premised issue (rc=$W3_RC): $W3_OUT"
fi

say "FAULT W4 (ADR-005): unreadable ledger must degrade visibly, never exit 0/3"
cp .truth/claims.jsonl claims.w4.bak
echo 'this is not json' >> .truth/claims.jsonl
W4_ERR=$($T impact w.txt 2>&1 >/dev/null) && W4_RC=0 || W4_RC=$?
if ! grep -q 'this is not json' .truth/claims.jsonl; then
  miss "fault injection failed: ledger was never corrupted"
elif [ "$W4_RC" -ne 0 ] && [ "$W4_RC" -ne 3 ] && echo "$W4_ERR" | grep -q "not valid JSON"; then
  ok "corrupted ledger degraded visibly (rc=$W4_RC), not silently"
else
  miss "impact on corrupt ledger wrong (rc=$W4_RC): $W4_ERR"
fi
mv claims.w4.bak .truth/claims.jsonl

say "FAULT S1 (spec-health): spec citing only live/open ids must pass"
mkdir -p docs/specs
printf '# Spec: canary good\ncites %s and %s\n' "$CID_R" "$WK_DEP" > docs/specs/good.md
if bash scripts/spec-health.sh >/dev/null 2>&1; then
  ok "healthy spec passed (live claim $CID_R, open issue $WK_DEP)"
else
  miss "spec-health failed a spec citing only live/open ids"
fi

say "FAULT S2 (spec-health): spec standing on a dead fact must fail"
if ! $T list --stale --json | grep -q "$CID_B"; then
  miss "fault injection failed: $CID_B is not stale, S2 cannot run armed"
else
  printf '# Spec: canary bad\nstands on %s\n' "$CID_B" > docs/specs/bad.md
  S2_OUT=$(bash scripts/spec-health.sh 2>&1) && S2_RC=0 || S2_RC=$?
  if [ "$S2_RC" -ne 0 ] && echo "$S2_OUT" | grep -q "FAIL  $CID_B"; then
    ok "spec on stale $CID_B failed with exit $S2_RC"
  else
    miss "spec-health passed a spec standing on stale $CID_B (rc=$S2_RC)"
  fi
  rm -f docs/specs/bad.md
fi

say "FAULT S3 (spec-health): zero-id spec must WARN but not fail"
printf '# Spec: canary unwired\nprose with no ids\n' > docs/specs/unwired.md
S3_OUT=$(bash scripts/spec-health.sh 2>&1) && S3_RC=0 || S3_RC=$?
if [ "$S3_RC" -eq 0 ] && echo "$S3_OUT" | grep -q "WARN  no ledger ids cited"; then
  ok "unwired spec warned without failing the sweep"
else
  miss "unwired spec handling wrong (rc=$S3_RC): $(echo "$S3_OUT" | tail -2)"
fi
rm -rf docs/specs

say "FAULT S4 (spec-health, ADR-003): issues-side degradation must announce and continue, not crash"
mkdir -p docs/specs
printf '# Spec: canary degraded\ncites %s and %s\n' "$CID_R" "$WK_DEP" > docs/specs/degraded.md
mv scripts/truth scripts/truth.real
cat > scripts/truth <<'SH'
#!/usr/bin/env bash
[ "${1:-}" = "issues" ] && { echo "truth: simulated issues failure" >&2; exit 1; }
exec python3 "$(dirname "$0")/truth.real" "$@"
SH
chmod +x scripts/truth
if scripts/truth issues --json >/dev/null 2>&1; then
  miss "fault injection failed: wrapped truth still serves issues --json"
else
  S4_OUT=$(bash scripts/spec-health.sh 2>&1) && S4_RC=0 || S4_RC=$?
  if echo "$S4_OUT" | grep -q "treating issue records as absent" \
     && echo "$S4_OUT" | grep -q "ok    $CID_R" \
     && echo "$S4_OUT" | grep -q "FAIL  $WK_DEP  missing" \
     && echo "$S4_OUT" | grep -q "spec-health: .* failure(s)"; then
    ok "degraded sweep announced on stderr, still judged claims, wk- reported missing (rc=$S4_RC)"
  else
    miss "spec-health degradation wrong (rc=$S4_RC): $(echo "$S4_OUT" | tail -3)"
  fi
fi
mv -f scripts/truth.real scripts/truth
rm -rf docs/specs

say "FAULT D1 (doc-health): clean corpus must pass; absent patterns file must only skip check A"
mkdir -p docs
printf '# target\n' > docs/target.md
printf '# live\nsee [target](target.md)\n' > docs/live.md
git add docs/target.md docs/live.md
D1_OUT=$(bash scripts/doc-health.sh 2>&1) && D1_RC=0 || D1_RC=$?
if [ "$D1_RC" -eq 0 ] && echo "$D1_OUT" | grep -q "0 failure(s)" \
   && echo "$D1_OUT" | grep -q "name-pattern check skipped"; then
  ok "clean corpus passed, patterns check skipped gracefully"
else
  miss "doc-health wrong on clean corpus (rc=$D1_RC): $(echo "$D1_OUT" | tail -2)"
fi

say "FAULT D2 (doc-health): broken relative link must fail"
printf '# live2\nsee [gone](no-such-file-xyz.md)\n' > docs/live2.md
git add docs/live2.md
if ! grep -q "no-such-file-xyz" docs/live2.md; then
  miss "fault injection failed: broken link was never seeded"
else
  D2_OUT=$(bash scripts/doc-health.sh 2>&1) && D2_RC=0 || D2_RC=$?
  if [ "$D2_RC" -ne 0 ] && echo "$D2_OUT" | grep -q "broken link 'no-such-file-xyz.md'"; then
    ok "broken link failed with exit $D2_RC"
  else
    miss "doc-health passed a broken link (rc=$D2_RC)"
  fi
fi
git rm -q --cached docs/live2.md && rm -f docs/live2.md

say "FAULT D3 (doc-health): forbidden name pattern must fail when patterns file exists"
printf '# forbidden names\nold[-_]widget\n' > scripts/doc-health.patterns
printf '# live3\nthe old-widget component\n' > docs/live3.md
git add docs/live3.md
if ! grep -q "old-widget" docs/live3.md; then
  miss "fault injection failed: forbidden name was never seeded"
else
  D3_OUT=$(bash scripts/doc-health.sh 2>&1) && D3_RC=0 || D3_RC=$?
  if [ "$D3_RC" -ne 0 ] && echo "$D3_OUT" | grep -q "forbidden name 'old-widget'"; then
    ok "forbidden name failed with exit $D3_RC"
  else
    miss "doc-health missed a forbidden name (rc=$D3_RC): $(echo "$D3_OUT" | tail -2)"
  fi
fi
git rm -q --cached docs/live3.md docs/target.md docs/live.md
rm -f docs/live3.md docs/target.md docs/live.md scripts/doc-health.patterns

# ---- FAULT N (v0.4): mid-file insertion must block the commit -------------
say "FAULT N (INV-A strict): mid-file insertion (pure addition) must be blocked"
git add -A && git commit -qm "canary: settle before insertion" --no-verify
python3 - <<'PYEOF'
import json
lines=open(".truth/claims.jsonl").readlines()
forged={"id":"tr-deadbeef","kind":"claim","actor":"agent-x","session":"s-evil",
        "ts":"2020-01-01T00:00:00+00:00",
        "payload":{"text":"forged backdated record","evidence_class":"UNVERIFIED",
                   "cost_tier":"P2","ttl_days":None,"evidence_paths":[]}}
lines.insert(0, json.dumps(forged,sort_keys=True)+"\n")
open(".truth/claims.jsonl","w").writelines(lines)
PYEOF
git add .truth/claims.jsonl
if bash scripts/check-truth.sh >/dev/null 2>&1; then
  miss "gate accepted a mid-file insertion (additions-only tampering)"
else
  ok "gate blocked the mid-file insertion"
fi
git checkout -q -- .truth/claims.jsonl

say "FAULT A (INV-A): mutating a historical ledger line must block the commit"
git add -A && git commit -qm "canary: settle ledger" --no-verify
# -i.bak is the only sed -i form GNU and BSD/macOS sed both accept
sed -i.bak '1s/claim/CLAIM_TAMPERED/' .truth/claims.jsonl && rm -f .truth/claims.jsonl.bak
git add .truth/claims.jsonl
if ! grep -q CLAIM_TAMPERED .truth/claims.jsonl; then
  miss "fault injection failed: ledger line was never mutated (sed)"
elif bash scripts/check-truth.sh >/dev/null 2>&1; then
  miss "check-truth.sh allowed a mutated historical record"
else
  ok "check-truth.sh blocked the tampered ledger"
fi
git checkout -q -- .truth/claims.jsonl

# ======================================================= sandbox 2 (G1)
say "FAULT F (G1): VERIFIED claim in a zero-commit repo must be refused"
mkrepo "$TMP2"
echo x > f.txt
if $T claim "f.txt exists" --class VERIFIED --evidence-cmd "cat f.txt" \
     --paths "f.txt" --tier P0 2>/dev/null; then
  miss "intake anchored a claim in a repo with no commits"
else
  ok "intake refused: no commits, no anchor"
fi

# ======================================================= sandbox 3 (G14)
say "FAULT E (G14): erased anchor commit must invalidate, with reason"
mkrepo "$TMP3"
echo data > g.txt
git add -A && git commit -qm "canary: init"
CID_E=$($T claim "g.txt says data" --class VERIFIED \
        --evidence-cmd "cat g.txt" --paths "g.txt" --tier P0)
TRUTH_SESSION=s-canary-verifier $T verdict "$CID_E" agree --basis "canary: verified at filing" >/dev/null
git checkout -q --orphan rewritten
git add -A && git commit -qm "canary: history rewritten"
git branch -D main -q
git reflog expire --expire=now --expire-unreachable=now --all
git gc --prune=now -q
$T invalidate-scan --quiet
if $T list --stale --json | grep -q "$CID_E" && \
   grep -q "anchor unreachable" .truth/claims.jsonl; then
  ok "claim $CID_E stale with reason 'anchor unreachable'"
else
  miss "history rewrite left $CID_E trusted or unexplained"
fi

say ""
say "canary result: $PASS caught, $FAIL missed"
if [ "$FAIL" -gt 0 ]; then
  say "CANARY FAILED -- the immune system has a hole."
  exit 1
fi
say "ALL CANARIES CAUGHT."
