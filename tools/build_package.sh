#!/bin/zsh
# build_package.sh -- assemble the delivery folder handed to the studio.
#
# The repository is organised for the audit; this is organised for the person
# who has to act on it. Folders are numbered in the order someone actually
# needs them: read the report, ship the data fix, optionally replace the
# matcher, check the evidence if they want to.
#
# Regenerates from scratch every time, so the package can never drift from the
# repository state that produced it.

set -e
REPO="$HOME/chatguard"
OUT="$HOME/Desktop/Chat-Filter-Audit"

rm -rf "$OUT"
mkdir -p "$OUT"/{1-report,2-quick-fix,3-replacement-engine,4-evidence}

# ---- 1 report ------------------------------------------------------------
cp "$REPO/docs/chat-filter-audit-report.pdf"   "$OUT/1-report/Chat-Filter-Audit-Report.pdf"
cp "$REPO/docs/chat-filter-defect-report.pdf"  "$OUT/1-report/Summary-One-Page.pdf"
cp "$REPO/REPORT.md"                           "$OUT/1-report/report.md"
cp "$REPO/docs/SUGGESTIONS.md"                 "$OUT/1-report/suggestions-not-audit-findings.md"
cp "$REPO/docs/method-team-channel.png"        "$OUT/1-report/how-it-was-measured.png"

# ---- 2 quick fix: the data + the three-line shim -------------------------
cp "$REPO/findings/words-to-allow.txt"  "$OUT/2-quick-fix/"
cp "$REPO/findings/affected-words.txt"  "$OUT/2-quick-fix/"
cp "$REPO/fix/allowlist-en.txt"         "$OUT/2-quick-fix/"
cp "$REPO/fix/rescue.py"                "$OUT/2-quick-fix/"
cp "$REPO/fix/DEPLOY.md"                "$OUT/2-quick-fix/"

# ---- 3 replacement matcher ----------------------------------------------
cp "$REPO/engine/chatguard.py" "$REPO/engine/shadow.py" "$OUT/3-replacement-engine/"
cp -R "$REPO/engine/tests"   "$OUT/3-replacement-engine/tests"
cp -R "$REPO/engine/vectors" "$OUT/3-replacement-engine/vectors"
cp "$REPO/tools/conformance.py"     "$OUT/3-replacement-engine/"
cp "$REPO/tools/safety_screen.py"   "$OUT/3-replacement-engine/"
cp "$REPO/tools/blackbox.py"        "$OUT/3-replacement-engine/"
cp "$REPO/tools/selftest_filter.py" "$OUT/3-replacement-engine/"
cp "$REPO/tools/build_lexicon.py"   "$OUT/3-replacement-engine/"

cp -R "$REPO/engine/lexicon" "$OUT/3-replacement-engine/lexicon"
find "$OUT" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

# The package flattens the repository's engine/ and tools/ into one directory, so the copied scripts' sys.path lines no longer
# describe where they live. Rewritten here rather than in the repo, because the
# repo layout is correct for the repo -- a package whose own test suite cannot
# run is not a deliverable.
/usr/bin/sed -i '' \
  -e 's|^ENGINE = .*|ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))|' \
  -e 's|^ROOT = os.path.dirname(ENGINE)|ROOT = ENGINE|' \
  -e 's|os.path.join(ROOT, "tools")|ROOT|' \
  -e 's|self._run("tools/|self._run("|g' \
  "$OUT/3-replacement-engine/tests/test_all.py"
/usr/bin/sed -i '' \
  -e 's|os.path.join(os.path.dirname(__file__), "..", "engine")|os.path.dirname(os.path.abspath(__file__))|' \
  "$OUT/3-replacement-engine/conformance.py"
# verify_safe.py sits at the package root so it can see BOTH shipped parts --
# the quick-fix shim and the engine. Pointing it at one subfolder made it find
# nothing and print PASS having read no code.
cp "$REPO/tools/verify_safe.py" "$OUT/verify_safe.py"
/usr/bin/sed -i '' \
  -e 's|^ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))|ROOT = os.path.dirname(os.path.abspath(__file__))|' \
  -e 's|"fix/rescue.py"|"2-quick-fix/rescue.py"|' \
  -e 's|"engine/chatguard.py"|"3-replacement-engine/chatguard.py"|' \
  -e 's|"engine/shadow.py"|"3-replacement-engine/shadow.py"|' \
  -e 's|("engine/shadow.py", "dump")|("3-replacement-engine/shadow.py", "dump")|' \
  "$OUT/verify_safe.py"
/usr/bin/sed -i '' \
  -e 's|os.path.join(os.path.dirname(__file__), "..", "engine", "vectors", "golden.jsonl")|os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors", "golden.jsonl")|' \
  "$OUT/3-replacement-engine/conformance.py"

# ---- 4 evidence ----------------------------------------------------------
cp "$REPO/findings/findings.json"     "$OUT/4-evidence/"
cp "$REPO/findings/blocked-terms.txt" "$OUT/4-evidence/"
cp -R "$REPO/findings/raw-logs"       "$OUT/4-evidence/raw-logs"

cp "$REPO/tools/package-readme.md" "$OUT/READ-ME-FIRST.md"

cd "$HOME/Desktop" && rm -f Chat-Filter-Audit.zip
zip -qr Chat-Filter-Audit.zip Chat-Filter-Audit -x '*.DS_Store'

echo "package: $OUT"
du -sh "$OUT" | awk '{print "  size:", $1}'
echo "  archive: $HOME/Desktop/Chat-Filter-Audit.zip"
find "$OUT" -type f | wc -l | awk '{print "  files:", $1}'
