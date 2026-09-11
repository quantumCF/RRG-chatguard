#!/usr/bin/env python3
"""
marathon.py -- long unattended probe run. Resumable, self-healing.

Designed to be left alone for 14 hours with nobody watching:

  * resumes from the log, so a restart never repeats work or loses it
  * clears the client's idle lock on its own
  * waits rather than dies when the game window is missing (crash, update)
  * flushes every result immediately, so a kill at any instant costs one probe
  * stops at a hard deadline

The supervisor (supervise.sh) restarts this if it dies or stalls, so the only
job here is to make progress and never block forever.
"""
import json, os, random, re, subprocess, sys, time
import Quartz, Vision
from Foundation import NSURL

SP = os.path.dirname(os.path.abspath(__file__))
LOG = os.environ.get("MARATHON_LOG", os.path.join(SP, "marathon-results.jsonl"))
HEARTBEAT = os.path.join(SP, "marathon.heartbeat")
QUEUE = os.environ.get("MARATHON_QUEUE", os.path.join(SP, "marathon.txt"))
DEADLINE_FILE = os.path.join(SP, "marathon.deadline")

INPUT_XY = (792, 964)
SEND_XY = (1060, 964)
UNLOCK_XY = (930, 946)
CONS = "bcdfghjkmnpqrstvwxz"


def sh(*a):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return ""


def win_bounds():
    out = sh("osascript", "-e",
             'tell application "System Events" to tell process "RagnarokRebirth" '
             'to get {position, size} of window 1').strip()
    n = [int(v) for v in re.findall(r"-?\d+", out)]
    if len(n) >= 4 and n[2] > 300 and n[3] > 300:
        return tuple(n[:4])
    return None


def wait_for_window(max_wait=1800):
    """The app may crash or update. Wait it out instead of dying."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        b = win_bounds()
        if b:
            return b
        if not sh("pgrep", "-f", "RagnarokRebirth").strip():
            subprocess.run(["open", "-a", "Ragnarok: Rebirth"], capture_output=True)
        time.sleep(20)
    return None


def activate():
    sh("osascript", "-e", 'tell application "System Events" to set frontmost '
       'of process "RagnarokRebirth" to true')
    time.sleep(0.22)


def click(x, y):
    for k in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                           Quartz.CGEventCreateMouseEvent(None, k, (x, y),
                                                          Quartz.kCGMouseButtonLeft))
        time.sleep(0.04)
    time.sleep(0.14)


def key(code, cmd=False):
    for down in (True, False):
        ev = Quartz.CGEventCreateKeyboardEvent(None, code, down)
        if cmd:
            Quartz.CGEventSetFlags(ev, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.022)


def drag(x0, y0, x1, y1, steps=22):
    for k, pt in ((Quartz.kCGEventMouseMoved, (x0, y0)),
                  (Quartz.kCGEventLeftMouseDown, (x0, y0))):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                           Quartz.CGEventCreateMouseEvent(None, k, pt,
                                                          Quartz.kCGMouseButtonLeft))
        time.sleep(0.08)
    for i in range(1, steps + 1):
        p = (x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                           Quartz.CGEventCreateMouseEvent(
                               None, Quartz.kCGEventLeftMouseDragged, p,
                               Quartz.kCGMouseButtonLeft))
        time.sleep(0.011)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                       Quartz.CGEventCreateMouseEvent(
                           None, Quartz.kCGEventLeftMouseUp, (x1, y1),
                           Quartz.kCGMouseButtonLeft))
    time.sleep(0.35)


def grab(tag, region=None):
    b = win_bounds()
    if not b:
        return None
    x, y, w, h = b
    if region:
        fx0, fy0, fx1, fy1 = region
        x += int(w * fx0); y += int(h * fy0)
        w = int(w * (fx1 - fx0)); h = int(h * (fy1 - fy0))
    p = os.path.join(SP, f"m_{tag}.png")
    try:
        subprocess.run(["screencapture", "-x", "-o", f"-R{x},{y},{w},{h}", p],
                       capture_output=True, timeout=20)
    except Exception:
        return None
    return p if os.path.exists(p) else None


def ocr(path):
    if not path:
        return []
    try:
        url = NSURL.fileURLWithPath_(path)
        src = Quartz.CGImageSourceCreateWithURL(url, None)
        if src is None:
            return []
        img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)
        req.setUsesLanguageCorrection_(False)
        h = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
        h.performRequests_error_([req], None)
        return [o.topCandidates_(1)[0].string() for o in (req.results() or [])
                if o.topCandidates_(1)]
    except Exception:
        return []


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def unlock_if_needed():
    t = " ".join(ocr(grab("lk", (0.0, 0.90, 1.0, 1.0)))).lower()
    if "swipe" in t or "unlock" in t:
        x, y = UNLOCK_XY
        for dy in (0, -20, -38):
            drag(x - 60, y + dy, x + 80, y + dy)
            time.sleep(0.3)
            t = " ".join(ocr(grab("lk", (0.0, 0.90, 1.0, 1.0)))).lower()
            if "swipe" not in t and "unlock" not in t:
                return True
        return True
    return False


_n = [0]


def next_tag():
    _n[0] += 1
    v = _n[0] + int(time.time()) % 997
    L = len(CONS)
    return CONS[v % L] + CONS[(v // L) % L] + CONS[(v // (L * L)) % L]


def probe(text, retries=1, confirm=True):
    if not wait_for_window(600):
        return {"text": text, "result": "nowindow"}
    activate()
    _n[0] += 1
    if _n[0] % 8 == 1 or retries == 0:
        unlock_if_needed()

    tag = next_tag()
    payload = f"{tag} {text}"
    click(*INPUT_XY)
    key(0, cmd=True); time.sleep(0.07); key(51); time.sleep(0.07)
    subprocess.run(["pbcopy"], input=payload.encode(), check=False)
    time.sleep(0.09)
    key(9, cmd=True)
    time.sleep(0.26)

    shown = norm(" ".join(ocr(grab("i", (0.05, 0.92, 0.75, 1.0)))))
    if norm(payload)[:8] not in shown:
        if retries:
            time.sleep(0.5)
            return probe(text, retries - 1, confirm)
        return {"text": text, "result": "mismatch"}

    click(*SEND_XY)
    present = False
    for wait in (1.2, 0.9):
        time.sleep(wait)
        blob = norm(" ".join(ocr(grab("h", (0.10, 0.55, 0.82, 0.92)))))
        w = norm(text)
        if tag in blob or (len(w) >= 4 and w in blob):
            present = True
            break
    if present:
        return {"text": text, "result": "sent"}
    if confirm:
        again = probe(text, 1, confirm=False)
        if again.get("result") == "sent":
            return {"text": text, "result": "sent", "note": "flaky"}
    return {"text": text, "result": "blocked"}


def main():
    deadline = float(open(DEADLINE_FILE).read().strip()) \
        if os.path.exists(DEADLINE_FILE) else time.time() + 14 * 3600

    done = set()
    if os.path.exists(LOG):
        for line in open(LOG, encoding="utf-8"):
            try:
                done.add(json.loads(line)["text"])
            except Exception:
                pass

    queue = []
    for line in open(QUEUE, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if parts and parts[0] and parts[0] not in done:
            queue.append((parts[0], parts[1] if len(parts) > 1 else "?"))

    print(f"resuming: {len(done)} done, {len(queue)} remaining, "
          f"{(deadline - time.time())/3600:.1f}h left", flush=True)

    with open(LOG, "a", encoding="utf-8") as fh:
        for i, (text, tag) in enumerate(queue, 1):
            if time.time() > deadline:
                print("DEADLINE REACHED", flush=True)
                break
            r = probe(text)
            r["tag"] = tag
            r["t"] = int(time.time())
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            open(HEARTBEAT, "w").write(str(int(time.time())))
            if i % 50 == 0:
                print(f"  {i}/{len(queue)}  {(deadline-time.time())/3600:.1f}h left",
                      flush=True)
            if r["result"] == "nowindow":
                time.sleep(30)
            time.sleep(random.uniform(0.4, 0.9))
    print("RUN COMPLETE", flush=True)


if __name__ == "__main__":
    main()
