#!/usr/bin/env python3
"""Minimal cross-family review gate for a repo that vendors no full gate.

Preston, 2026-09-22: "add the xfam review or my waiver ruling to all repos."
routabout, dudvault, actionable-intel and dudley-travel each carry the full
`scripts/check_xfam_review.py`, with a per-repo HIGH_RISK table built from that
repo's own history. This file is the portable stand-in for the repos that carry
no gate at all and had no CI whatsoever: it asks the same question with a much
smaller classifier, and deliberately does NOT try to reproduce the big table.

WHAT IT DOES. Lists the paths a PR changes against its base, keeps the ones in a
high-risk class, and then requires the PR body to carry EITHER an independent
cross-family review record OR Preston's waiver line. No high-risk path, no
requirement — an ordinary docs or content PR passes untouched.

WHAT SATISFIES IT
  * a `## Cross-family review` section naming a reviewer and an outcome; or
  * `Cross-family review: not required — <reason>` (a substantive reason: a
    bare "not required" is refused).

WHAT IT DOES NOT DO. It does not verify receipts (these repos have no signing
key), does not check reviewer-family independence against a declared author
family, and does not pin a reviewed head SHA. Those live in the full gate. A
repo that grows real enforcement code should graduate to that file rather than
extend this one.

`--name-only -z`: git C-quotes a path containing a quote, a backslash or a
non-ASCII byte and returns it WITH the quotes, which silently defeats every
anchored pattern below. The `-z` form is NUL-separated and never quoted. That
bug shipped in the full gate and was fixed 2026-09-22 (routabout #4220,
dudvault #513); this file is written with the fix from the start.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# PROSE IS NOT ENFORCEMENT. Several of these repos are documentation
# repositories: a note named `docs/deletion-policy.md` or `authoring.md` is
# writing ABOUT a subject, not code that enforces it. Classifying prose here
# would fire on ordinary work and teach people to waive reflexively, which is
# the failure mode the doctrine's own gates warn about — so prose is excluded
# BEFORE classification, except under `.github/` where a "doc" can still be
# configuration. Raised by the cross-family review of this file, 2026-09-22.
PROSE = re.compile(r"\.(md|markdown|txt|rst|adoc)$", re.IGNORECASE)

# The list below is COMMON extensions, not an exhaustive one. An unusual
# presentational extension (`.tiff`, `.fon`) still classifies if its name
# carries a topic word, and that is the safe direction: the gate asks for a
# one-line record instead of staying silent. Extend it when a real path proves
# noisy, not pre-emptively.
#
# PRESENTATION IS NOT ENFORCEMENT EITHER. Three of these repos are static
# sites, where `privacy-policy.tsx` is a PAGE about privacy and `StripeLogo.tsx`
# is an image component. Topic words in presentational files are subject matter,
# not the code that enforces the subject, so TOPICAL patterns below skip them.
# STRUCTURAL patterns (a migration, a workflow, a Dockerfile, `.env.example`)
# still fire regardless of extension, because those ARE the mechanism. Both
# false-positive classes were found by the cross-family review of this file,
# 2026-09-22 — a gate that cries wolf on ordinary content teaches reflexive
# waiving, which is worse than no gate.
PRESENTATION = re.compile(
    r"\.(tsx|jsx|vue|svelte|css|scss|sass|less|html?|svg|png|jpe?g|gif|webp|avif|bmp|ico"
    r"|woff2?|ttf|otf|eot|mp4|webm|mp3|wav|pdf)$",
    re.IGNORECASE,
)

# Structure: the path IS the mechanism. Always classified.
STRUCTURAL: tuple[tuple[str, str], ...] = (
    (r"(^|/)migrations?/", "database migration"),
    (r"(^|/)supabase/migrations/", "database migration"),
    (r"(^|/)\.github/(workflows|actions)/", "production infrastructure"),
    # Variants matter: `Dockerfile.prod`, `compose.yml`, `docker-compose.override.yml`.
    (r"(^|/)Dockerfile(\.[A-Za-z0-9_.-]+)?$"
     r"|(^|/)(docker-)?compose(\.[A-Za-z0-9_-]+)?\.ya?ml$", "production infrastructure"),
    (r"\.env\.example$", "authentication"),
    (r"policies?\.sql$|row_level_security", "authorization/RLS"),
)

# Topic: the NAME suggests the subject. Word-ish boundaries on purpose — an
# unanchored `auth` classified `docs/authoring.md`, and `(^|/)webhooks?/` missed
# `stripe_webhook.py`. Skipped for prose and presentational files.
TOPICAL: tuple[tuple[str, str], ...] = (
    (r"(^|[/_.-])(auth|authn|authz|oauth|session|login|signin"
     r"|authentication|authorization)([/_.-]|$)", "authentication"),
    (r"(^|[/_.-])webhooks?([/_.-]|$)", "payments"),
    (r"(^|[/_.-])(billing|checkout|payments?|stripe|subscription)([/_.-]|$)", "payments"),
    (r"(^|[/_.-])consents?([/_.-]|$)", "consent"),
    (r"(^|[/_.-])entitlements?([/_.-]|$)", "authorization/RLS"),
    (r"(^|[/_.-])rls([/_.-]|$)", "authorization/RLS"),
    (r"(^|[/_.-])privacy([/_.-]|$)", "privacy"),
    (r"(^|[/_.-])(deletion|retention|erasure)([/_.-]|$)", "deletion and export"),
    (r"(^|[/_.-])(credentials?|secrets?)([/_.-]|$)", "authentication"),
    (r"(^|[/_.-])(minors?|guardian|under13|coppa)([/_.-]|$)", "minors and school safety"),
)

# A heading, a named reviewer and an outcome. Same shape the full gate's
# `attested()` looks for, minus the head-SHA and family checks it also does.
_HEADING = re.compile(r"^\s*#{1,4}\s*cross-family review\b", re.IGNORECASE | re.MULTILINE)
# Line-anchored, so a mention inside a sentence ("the reviewing family was…")
# is not mistaken for a record. The documentation says "a line"; this makes that
# true rather than approximately true.
_REVIEWER = re.compile(r"^\s*\**\s*review(?:er|ing)\s*:\s*\S.{9,}",
                       re.IGNORECASE | re.MULTILINE)
_OUTCOME = re.compile(
    r"^\s*\**\s*(material concerns|disposition|verdict)\s*:\s*\S.{4,}",
    re.IGNORECASE | re.MULTILINE,
)
# The trailing text is required: a bare "not required" records no reason and so
# cannot be reviewed later. This is a LENGTH check (ten characters or more), not
# a judgement of whether the reason is good — a human reads that on the PR.
# Line-anchored like the reviewer/outcome patterns: a waiver is a DECLARATION,
# so it must stand on its own line. Prose mentioning the syntax — "I assert
# Cross-family review: not required — …" mid-sentence, or a line quoting it
# while explaining it — is not a waiver. Found by the cross-family review of
# this file, 2026-09-22; the full gate learned the same lesson on PR #497.
_EXEMPT = re.compile(
    r"^\s*\**\s*cross-family review:\s*not required\s*[—\-–:]\s*\S.{9,}",
    re.IGNORECASE | re.MULTILINE,
)


def changed_paths(base: str) -> list[str]:
    merge_base = subprocess.run(
        ["git", "merge-base", base, "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    out = subprocess.run(
        ["git", "--literal-pathspecs", "diff", "--name-only", "-z", merge_base, "HEAD"],
        capture_output=True, check=True,
    ).stdout
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def in_class(paths: list[str]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for path in paths:
        for pattern, cls in STRUCTURAL:
            if re.search(pattern, path, re.IGNORECASE):
                hits.append((path, cls))
        if path.startswith(".github/"):
            continue  # already covered structurally; its prose is not topical
        if PROSE.search(path) or PRESENTATION.search(path):
            continue
        for pattern, cls in TOPICAL:
            if re.search(pattern, path, re.IGNORECASE):
                hits.append((path, cls))
    return hits


def attested(body: str) -> bool:
    return bool(_HEADING.search(body) and _REVIEWER.search(body) and _OUTCOME.search(body))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--body-file")
    ap.add_argument("--paths", nargs="*", help="classify these paths instead of git (tests)")
    args = ap.parse_args()

    paths = args.paths if args.paths is not None else changed_paths(args.base)
    hits = in_class(paths)

    print("── cross-family review gate (minimal) ──")
    if not hits:
        print("✓ no high-risk-class paths in this diff — cross-family review not triggered")
        return 0

    classes = sorted({cls for _p, cls in hits})
    print(f"  {len({p for p, _c in hits})} changed path(s) in {len(classes)} high-risk "
          f"class(es): {', '.join(classes)}")
    for path, cls in sorted(set(hits)):
        print(f"    {path}  [{cls}]")

    body = ""
    if args.body_file:
        with open(args.body_file, encoding="utf-8", errors="replace") as fh:
            body = fh.read()

    if _EXEMPT.search(body):
        print("\n✓ PR body records an explicit exemption with a reason — gate satisfied.")
        return 0
    if attested(body):
        print("\n✓ PR body carries a Cross-family review section naming a reviewer and an "
              "outcome — gate satisfied.")
        print("  (This minimal gate does not check reviewer family or reviewed head SHA;"
              " a human reads those.)")
        return 0

    print("\n✗ BLOCKED — no cross-family review record on an in-class PR.")
    print("  CROSS_FAMILY_REVIEW_DOCTRINE.md (BINDING): a change in a high-risk class")
    print("  must be reviewed by a model family independent of the one that authored")
    print("  it, BEFORE merge, with the evidence on the PR.\n")
    print("  Add to the PR body either:")
    print("    ## Cross-family review")
    print("    Reviewing: <model/family>        (and how it was run)")
    print("    Material concerns: <findings, or none>")
    print("    Disposition: <what changed, what was rejected and why>\n")
    print("  or, when Preston rules it unnecessary, his waiver in his words:")
    print("    Cross-family review: not required — <specific reason>")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
