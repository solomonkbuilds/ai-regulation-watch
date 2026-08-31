# Classifier evaluation

## Why evaluate at all

The riskiest component in this pipeline isn't the scraping — it's the LLM
classification step that decides whether a detected change is AI-relevant.
Treating that decision as ground truth without checking it would be sloppy
for the same reason it's sloppy in GRC generally: any control (automated or
human) needs periodic testing against known cases, not just trust.

## Method

`tests/eval_set.jsonl` contains hand-labeled examples: a source name, a diff,
and an expected `ai_relevant` boolean. `tests/eval_classifier.py` runs the
live classifier against each example and reports accuracy.

Run it with:

```bash
python tests/eval_classifier.py
```

## Current results

_Run the eval script and paste the output here. Example format:_

| Metric | Value |
|---|---|
| Examples | 5 |
| Accuracy | — |
| False negatives | — |
| False positives | — |

## Known limitations

- The eval set is small (5 examples as of initial commit). Before relying on
  this classifier for anything beyond a portfolio demo, grow it to at least
  20-30 examples pulled from real detected changes.
- The classifier sees only the diff, not the full document context. A change
  that reads as AI-relevant in isolation might not be, and vice versa — this
  is a known tradeoff for keeping token usage low.
- Confidence scores are self-reported by the model, not calibrated against
  actual accuracy. A "high confidence" prediction should still be spot-checked
  periodically.

## How to extend the eval set

As the monitor runs against real sources, promising or surprising
classifications (especially anything the classifier got wrong on manual
review) should be added to `eval_set.jsonl` with the correct label. This
keeps the eval set grounded in real regulatory language rather than
synthetic examples.
