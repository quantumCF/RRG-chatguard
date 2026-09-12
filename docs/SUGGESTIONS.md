# Suggestions

**These are not audit findings.** Everything in `REPORT.md` and `findings/` was
measured against the live service. This file is different: it holds small chat
improvements worth considering while this area of the code is open. Each item
says plainly whether the audit supports it or whether it is only a suggestion.

Nothing here is required to fix the problem in the report.

---

## 1. Tell the player which word was rejected

**The audit supports this.** When the filter blocks a message, the player sees
a message saying the speech is inappropriate. It does not say which word caused
it. Because the cause is usually two letters inside an ordinary word, the
player cannot work out what to change, and cannot learn to avoid it. A player
who types `thanks` is told they were inappropriate, with no way to find out
why.

Showing the matched word, or masking it in place instead of rejecting the whole
message, would remove most of the confusion this causes. It also turns silent
repeat offences into something a player can correct.

`engine/` returns the matched span for this reason, so the text can be masked
rather than the message refused. See `Verdict.filtered` in
`engine/chatguard.py`.

---

## 2. Show a character counter on the chat input

**Suggestion. Not measured.** A live counter on the input box, showing
characters used against the limit, is standard in current chat clients. Players
currently reach the limit with no warning.

A counter is client-side only. It needs no server change, and it does not
affect moderation.

---

## 3. Raise the message length limit slightly

**Suggestion. Not measured.** A modest increase would let players finish a
normal sentence without splitting it across two messages. Splitting is more
likely than usual here, because a blocked message has to be rewritten before it
can be sent.

We did not measure the current limit, so this file does not name a target
number. Measuring it takes a minute: type into the chat box and note where the
input stops accepting characters.

A limit change is also client-side, with no effect on moderation.

---

## Why these are kept separate

The value of the report is that every figure in it can be traced to a record in
`findings/raw-logs/`. Suggestions cannot be traced that way, and mixing the two
would invite a reader to treat the measured findings as opinion. Keeping them
in a separate file costs one link and protects the rest.
