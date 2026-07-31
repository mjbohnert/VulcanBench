# Voice Eval Suite v1 — judge rubric

This rubric is the source of truth for the LLM judge used by
`harness/voice/scorer.py`. The judge prompt in code must stay in sync with
it; the judge model and version are pinned in every run manifest.

## Task

Given a question, a reference answer, and a candidate answer, decide whether
the candidate is **factually equivalent** to the reference.

## Rules

1. Ignore phrasing, verbosity, casing, punctuation, and number formatting
   ("88", "eighty-eight", and "the answer is 88" are all equivalent).
2. Extra *correct* context does not make an answer wrong ("Ottawa, the
   capital of Canada" matches "Ottawa").
3. A hedge between multiple candidates is wrong ("either 86 or 88").
4. A correct value with a wrong unit is wrong ("12 minutes" ≠ "12 meters");
   a missing unit is acceptable when the question fixes the unit.
5. For sequence answers (counting, lists in a required order), the order
   must match; separators and case do not matter.
6. Do not reward partial answers: if the question asks for a full sequence
   and half is given, it is wrong.

## Output

Respond with only a JSON object: `{"correct": true}` or `{"correct": false}`.

## Symmetry requirement

The identical scorer — normalization, matching, and this rubric — is applied
to text-mode and audio-mode responses. Any change to this rubric or the
judge prompt must be applied to both modes simultaneously (this is enforced
structurally: there is a single `score_response` entry point).
