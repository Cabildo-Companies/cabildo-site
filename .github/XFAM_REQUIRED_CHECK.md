# `Cross-family review` is a required check on `main`

Preston, 2026-09-22: "add the xfam review or my waiver ruling to all repos… do
the CI required check too."

`.github/workflows/xfam-review-gate.yml` runs `scripts/xfam_gate_min.py` — the
portable minimal gate, vendored here because this repo had no CI and no gate at
all — on every PR to `main`. Branch protection makes
the job's check, **`Cross-family review`**, required, and binds it to the
GitHub Actions app (`app_id 15368`).

## Why the app binding matters

A required check identified only by NAME can be satisfied by anything able to
post a commit status with that name — including a workflow added by the very PR
under review, since `pull_request` workflows run from the PR's own revision.
Binding the requirement to `app_id 15368` means only a GitHub Actions check run
counts, and the workflow that produces it is evaluated from the base branch
(`pull_request_target`). Both halves are needed: the base-branch trigger stops a
PR from rewriting the gate, and the app binding stops a PR from impersonating
its result. Raised by the cross-family review of this change, 2026-09-22.

## Intended protection for `main`

```json
{
  "required_status_checks": {
    "strict": true,
    "checks": [{ "context": "Cross-family review", "app_id": 15368 }]
  }
}
```

(Listed alongside this repo's existing required checks, which keep their own
bindings. `strict` is left as configured.)

## What satisfies the gate

The script decides, not the workflow. Exactly two things satisfy it:

1. a heading at any level (`#` to `####`) whose text begins `Cross-family
   review`, PLUS a `Reviewing:` or `Reviewer:` line, PLUS an outcome line
   (`Material concerns:`, `Disposition:` or `Verdict:`). The reviewer and
   outcome must each START A LINE (bold markers allowed), and each needs some
   text after the colon — at least ten characters for the reviewer, five for
   the outcome, so `Reviewing: AI` is refused as too thin to be a record. The
   parser checks that all three appear in the body; it does not require them to be adjacent
   or in that order, and it does not read what they say; or
2. Preston's waiver ON ITS OWN LINE: `Cross-family review: not required —
   <reason>`. An em dash, en dash, plain hyphen or colon all work as the
   separator. Prose that mentions the phrase mid-sentence is not a waiver. The
   check on the reason is a LENGTH check — ten characters or more — so a bare
   "not required" is refused, but nothing machine-judges whether the reason is
   a good one. That is deliberate: the waiver is durable and auditable on the
   PR, and a human reads it.

A PR touching no high-risk path passes untouched. Prose (`.md`, `.txt`, `.rst`,
`.adoc`) and a NAMED LIST of common presentational extensions — `.tsx`, `.jsx`,
`.vue`, `.svelte`, `.css`, `.scss`, `.sass`, `.less`, `.htm(l)`, `.svg`, `.png`,
`.jpg`/`.jpeg`, `.gif`, `.webp`, `.avif`, `.bmp`, `.ico`, `.woff`/`.woff2`,
`.ttf`, `.otf`, `.eot`, `.mp4`, `.webm`, `.mp3`, `.wav`, `.pdf` — are not
classified by the TOPICAL patterns: a page named `privacy-policy.tsx` is about
privacy, not the code enforcing it. The list is common extensions, **not
exhaustive**: an unusual one (`.tiff`, `.fon`) whose name carries a topic word
still classifies. That direction is deliberate — the gate asks for a one-line
record rather than staying silent — and the list should grow when a real path
proves noisy, not pre-emptively. STRUCTURAL
paths (anything under `migrations/` or `.github/workflows/`, a Dockerfile,
`.env.example`, `*policies.sql`) always classify, whatever the extension.

**Receipts are NOT a path here**, and this gate does not check reviewer-family
independence or pin a reviewed head SHA. The full `check_xfam_review.py` does
all three; this minimal one does not, and a human reads the record instead.

**The minimal gate is smaller than the full one** (`check_xfam_review.py`, which
routabout/dudvault/actionable-intel/dudley-travel carry): it does not verify
receipts, does not check reviewer-family independence against a declared author
family, and does not pin a reviewed head SHA. It asks for a review record or the
waiver and leaves judging those to a human. A repo that grows real enforcement
code should graduate to the full gate rather than extend this one.

## Rollout order matters

Merge the workflow FIRST, then make the check required. Reversed, the PR that
adds the workflow deadlocks: the base branch has no `pull_request_target`
workflow yet, so the required `Cross-family review` check can never report on
that PR and the merge is blocked with nothing able to unblock it. (Raised by the
cross-family review of this change, 2026-09-22.)

## Known limits (stated, not closed)

Both were raised by the cross-family review of this change and are properties of
GitHub and of a single-owner repository, not of this workflow:

1. **A required check binds to a NAME and an app, never to a workflow file.** A
   PR that adds a second workflow whose job is also named `Cross-family review`
   produces an Actions check run under that name, and GitHub accepts it. The
   base-branch trigger stops this gate from being edited, and the app binding
   stops a plain status from impersonating it, but neither can stop a same-named
   sibling job. What catches that is review of the PR that adds it — and, before
   the PR exists, `~/.claude/hooks/xfam-precommit-gate.sh`, which blocks the
   COMMIT that puts a new workflow file into a branch.
2. **The waiver line is an assertion, not a credential.** Nothing in CI proves
   Preston wrote `Cross-family review: not required — …`; anyone who can edit
   the PR body can write it. It is deliberately durable and auditable — it sits
   on the PR, in his words, with a reason — rather than authenticated. A
   mechanically authenticated waiver would need the same signing key receipts
   use (`XFAM_RECEIPT_KEY`), which this repo does not have.

Neither limit is a reason to skip the check: it turns the default from "nothing
looked" into "something looked, and bypassing it leaves a record".

## Direct pushes and automation

`enforce_admins` is deliberately left OFF. A required status check certainly
binds pull-request merges; how GitHub treats a DIRECT push to a branch with
required checks is not something this repo has tested, and some of these
repositories take direct pushes from the owner's own automation (cabildo-hq's
hourly arm-status commits, for instance). Leaving admin enforcement off keeps
those working either way, while every pull request is still bound — which is
where review belongs. The trade is stated
rather than hidden: an owner who merges with `--admin` can bypass this check,
and the commit-time hook (`xfam-precommit-gate.sh`) is what asks earlier.
