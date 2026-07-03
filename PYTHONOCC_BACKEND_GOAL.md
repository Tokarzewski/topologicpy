# Goal: Complete the PythonOCC Core backend for topologicpy

Make `src/topologicpy/pythonocc_backend/` pass topologicpy's `Core` backend
contract well enough that `Core.SetBackend(PythonOCCBackend)` is a real
drop-in replacement for `topologic_core` — not a demo.

## Ground truth

- Spec: `TopologicPy_Replacement_Backend_Developer_Guide.docx`. Read it in
  full — all tables via `python-docx`'s `d.tables`, not just paragraphs.
  Treat it as authoritative over anything below.
- Appendix A ("Minimum backend checklist") and §13 (test plan) define
  "done."
- Check `git log`/`git diff` in this repo before assuming anything is
  broken or missing — prior work has already landed some fixes. Trust
  what you observe over any stale summary, including this one.

## What matters most

Judge priority by how much of the checklist a fix unlocks, not by a fixed
list. As a compass:
- Non-manifold `CellComplex` (real shared faces across multiple cells) is
  the single most important behavior in Topologic — if it's faked (e.g.
  wrapping a single Cell), that's the highest-value fix.
- The guide's type IDs are bit flags, not sequential (Vertex=1, doubling
  per type up to Topology=4096) — get this right early since much else
  dispatches on it.
- Anything the guide defines as able to "fail" must return `None`, not an
  empty/sentinel object.
- Prefer a smaller surface that's real and tested over broad stub
  coverage.

## Freedom

Decide what to fix and in what order, as long as you move the checklist
forward without regressing what already works. Use your own judgment on
trade-offs — no external list here is mandatory.

## Constraints

- Work only in `pythonocc_backend/` — don't touch the abandoned
  `PythonOCCBackend.py` single-file version.
- Don't touch the Mojo repos (`topokernel`/`geokernel`) — separate effort,
  see `C:\Github\DigitalEngineer\topokernel\MOJO_BACKEND_GOAL.md`.
- Keep TopologicPy's analytical algorithms out of the backend — it's a
  primitive kernel + persistence layer only (guide §1).
- Run tests when PythonOCC is actually installed; say plainly when you
  can't verify rather than claiming untested code works.
- Don't commit; leave changes in the working tree for review.

## Acceptance

Appendix A's checklist and §13's test plan pass against
`Core.SetBackend(PythonOCCBackend)`, verified by actually running tests
with PythonOCC installed — not just code review.
