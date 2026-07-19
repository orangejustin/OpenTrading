# Two rules this codebase learned the hard way

Written after a run that produced nine defects in nine iterations. Every one of
them survived careful reasoning and passed whatever checks existed at the time.
They are recorded here because the pattern is more transferable than any of the
individual fixes.

## 1. Always run the thing

Not "review the diff". Not "the types line up". Execute the code path a user
would execute, and read what actually comes back.

The complete list from one branch:

| defect | why reasoning missed it |
|---|---|
| `ot risk ID --format json` had **never once parsed** | `--format` sat on the top-level parser, invisible after a subcommand. Manual testing used the text output, so it looked fine |
| the judge emitted a SHORT with `entry == stop` | schema-valid, semantically incoherent. No type system catches it |
| `claude_cli.generate_json` defaulted to `timeout=240`, not 300 | a signature patch silently missed while the body patch landed, leaving a function referencing a parameter it never declared. The unit check passed; the live call failed |
| `gex_sign` emits `positive/negative/flat`; the reader matched `long/short` | every negative-gamma tape rendered as "no strong dealer effect" — a plausible sentence, entirely wrong |
| `prior5` is a **fraction** | rendered raw, a judge read `-0.1331` as "-0.13%, basically flat" and dismissed the bear's case on what was a **13.31% collapse**. Traced to a real logged decision |
| `grade()` had no caller anywhere | the calibration panel looked identical whether the ledger was empty or merely never processed |
| TradingView relaunches **without** its debug port | `/json/version` answers once, then every CDP endpoint goes empty. Indistinguishable from a broken tool |

The common shape: **the code was reasonable and the world disagreed.** A wrong
unit, a vocabulary mismatch, a flag that never reached the parser. None of these
are logic errors you can think your way to.

Corollary: *"I verified this by reasoning about it"* is a null result. Say
"unverified" instead — it is more honest and it prompts the right next action.

## 2. Always measure the measurer

When you add a check, a gate, or a filter, the obvious question is "does it
run?" The useful question is **"how often does it fire, and would it catch the
thing it exists for?"** A check that always passes and a check that never fires
both look exactly like a working check.

Two from the same branch:

**A grounding verifier that would have waved through half of all
hallucinations.** It matched the judge's price levels against levels present in
the evidence, with a 1.5% tolerance. Correct in structure, and it passed the
real run 5/5. Measuring its discriminating power over the plausible price range:

    tol 0.5%  -> 22% of the range counts as "grounded"
    tol 1.5%  -> 49%          <- as shipped
    tol 3.0%  -> 69%

At 1.5% an arbitrary invented number had a coin-flip chance of passing.
Tightened to 0.75%.

**A divergence rule that was silent on its own use case.** Five sentiment
divergences, four firing 34–47% of the time across sampled market states —
informative. The fifth, price-vs-sentiment (the knife-vs-washout call, the most
decision-relevant of the set), fired **6.9%**, because it required `score < 35`
when the fear band boundary is 45. It failed to fire on live TQQQ at fear 37
with a −12.3% week: precisely the case it was written for. Retiered to 13.3%.

Both looked correct. Both passed every test reachable by inspection.

### Applied to tests

The same rule turns on tests themselves: a test that passes the moment you write
it has demonstrated nothing. Mutate the code, confirm the test fails, restore.
`tests/test_desk.py` was validated this way — reintroducing the loose tolerance,
the silent knife rule, and an unpaired RAM each produced the expected failure.

## Why this matters more here than elsewhere

This repo produces numbers a person uses to move money. A bug in a web app shows
up as a broken page; a bug in a scoring function shows up as **confident,
plausible, wrong advice** — and the more polished the output, the longer it
survives. Before the grading fixes, the desk reported a 77% hit rate on PUTs and
looked skilled. It was 50% with negative alpha.

Nothing about the output changed when the truth did. Only the measurement did.
