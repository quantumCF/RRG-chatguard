# Domain lexicons live here — generated, not shipped

This directory is intentionally empty.

The allowlist that protects a game's own content must come from that game's own
localization export, not from us. Generate it:

    python3 ../../tools/build_lexicon.py --locale en \
        --strings <your en localization, one string per line> --out .

Add `--cjk` for locales without word spacing (zh, ja, th) so that phrase
shelters are produced as well as word tokens — that is the only thing that can
rescue a single blocked Han character sitting inside an ordinary word.

Any `*.txt` placed here is picked up automatically by `tools/audit.py`.

Two reasons it works this way. It keeps this repository clean-room — no third
party's content is redistributed. And it removes the objection that an outsider
is making judgements about your language: nobody's judgement is involved, the
list is mechanically derived from strings you wrote.
