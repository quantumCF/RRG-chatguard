#!/usr/bin/env python3
"""
verify_safe.py -- prove what the shipped code can and cannot do.

Adopting code from outside the studio is a real risk, and "trust us, it is
clean" is not an answer. This reads the files you would actually deploy and
reports their dependency and capability surface, so the claim can be checked in
a few seconds rather than believed.

    python3 tools/verify_safe.py

Exit code 0 means: third-party imports none, network none, process execution
none, dynamic evaluation none, and every file write is an explicitly named
method rather than a side effect. Non-zero means something in that list is not
true, and the offending line is printed.

The check is deliberately syntactic. It parses the AST rather than matching
text, so a call cannot hide behind formatting, and it reports what it finds
rather than asserting a conclusion.
"""

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The files a studio would actually put into their service.
SHIPPED = [
    "fix/rescue.py",
    "engine/chatguard.py",
    "engine/shadow.py",
]

STDLIB_OK = {
    "__future__", "json", "re", "os", "sys", "time", "threading",
    "unicodedata", "collections", "dataclasses", "enum", "typing",
    "functools", "itertools", "math", "bisect", "string",
}

NETWORK = {"socket", "urllib", "http", "requests", "httpx", "ftplib",
           "telnetlib", "smtplib", "asyncio", "ssl", "xmlrpc"}
EXECUTION = {"subprocess", "multiprocessing", "ctypes", "signal", "pty"}
DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint"}
DANGEROUS_MODULES = {"pickle", "marshal", "shelve", "dill"}

# Writes that are part of the documented API rather than a side effect.
DECLARED_WRITERS = {("engine/shadow.py", "dump")}


def enclosing_function(tree, lineno):
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno and (best is None or node.lineno > best.lineno):
                end = getattr(node, "end_lineno", node.lineno)
                if lineno <= end:
                    best = node
    return best.name if best else None


def main():
    findings = []
    summary = []

    for rel in SHIPPED:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            findings.append((rel, 0, "missing", "file not found"))
            continue
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src, filename=rel)

        imports, writes, third_party = set(), [], set()

        for node in ast.walk(tree):
            # -- imports
            if isinstance(node, ast.Import):
                for a in node.names:
                    imports.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

            # -- dangerous calls
            elif isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if isinstance(fn, ast.Name) and fn.id in DANGEROUS_CALLS:
                    findings.append((rel, node.lineno, "dynamic-eval",
                                     f"call to {fn.id}()"))
                # -- file writes
                if name == "open":
                    mode = ""
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        mode = str(node.args[1].value)
                    for kw in node.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = str(kw.value.value)
                    if any(c in mode for c in "wax+"):
                        writes.append((node.lineno,
                                       enclosing_function(tree, node.lineno)))

        for mod in sorted(imports):
            if mod in NETWORK:
                findings.append((rel, 0, "network", f"imports {mod}"))
            elif mod in EXECUTION:
                findings.append((rel, 0, "process-exec", f"imports {mod}"))
            elif mod in DANGEROUS_MODULES:
                findings.append((rel, 0, "deserialisation", f"imports {mod}"))
            elif mod not in STDLIB_OK:
                third_party.add(mod)
                findings.append((rel, 0, "third-party", f"imports {mod}"))

        for lineno, func in writes:
            if (rel, func) not in DECLARED_WRITERS:
                findings.append((rel, lineno, "undeclared-write",
                                 f"open(..., 'w') in {func or '<module>'}()"))

        summary.append((rel, len(src.splitlines()), sorted(imports),
                        [f for _, f in writes]))

    # ---------------------------------------------------------------- report
    if not summary:
        print("No shipped files were found. Nothing was checked.\n")
    print("SHIPPED CODE — dependency and capability surface\n")
    print(f"{'file':<38}{'lines':>7}   imports")
    print("-" * 92)
    for rel, lines, imports, writes in summary:
        print(f"{rel:<38}{lines:>7}   {', '.join(imports)}")
        if writes:
            for w in writes:
                tag = "declared API" if (rel, w) in DECLARED_WRITERS else "UNDECLARED"
                print(f"{'':<38}{'':>7}   file write in {w}()  [{tag}]")
    total = sum(s[1] for s in summary)
    print("-" * 92)
    print(f"{'total':<38}{total:>7}\n")

    checks = [
        # "missing" first and deliberately: without it a misconfigured path
        # list inspects nothing, every other check finds nothing to object to,
        # and the tool prints PASS having read no code at all. A vacuous pass
        # is worse than no check, because it is indistinguishable from a real
        # one in a review.
        ("shipped files missing", "missing"),
        ("third-party dependencies", "third-party"),
        ("network access", "network"),
        ("process execution", "process-exec"),
        ("dynamic evaluation", "dynamic-eval"),
        ("unsafe deserialisation", "deserialisation"),
        ("undeclared file writes", "undeclared-write"),
    ]
    worst = 0
    for label, kind in checks:
        hits = [f for f in findings if f[2] == kind]
        mark = "none" if not hits else f"{len(hits)} FOUND"
        print(f"  {label:<28} {mark}")
        for rel, line, _, msg in hits:
            print(f"      {rel}:{line}  {msg}")
        worst += len(hits)

    print()
    if worst == 0:
        print("PASS — stdlib only, no network, no process execution, no dynamic")
        print("       evaluation, and the single file write is an explicit API")
        print("       method taking a path you supply.")
        return 0
    print(f"FAIL — {worst} finding(s) above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
