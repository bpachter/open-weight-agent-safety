# Open-Weight Agent Safety

Measurement infrastructure and results for indirect prompt-injection attacks
against locally-hosted open-weight language models.

**Papers**

1. *Unattacked, Not Unbreakable: Decomposing Prompt-Injection Success in
   Quantized Open-Weight Agents* —
   [`papers/01-unattacked-not-unbreakable/`](papers/01-unattacked-not-unbreakable/)

Everything here runs on one consumer GPU — a single RTX 24GB card serving
quantized models through Ollama. That is a deliberate constraint, not a
limitation to apologise for: it is the configuration that local agent
deployments actually use, and it is the one that cluster-scale research rarely
studies.

---

## What is being measured

An agent calls a tool. The tool returns content from somewhere the operator does
not control — a web page, a file, a database record. Somewhere in that content
is text addressed to the model rather than to the user.

The question is what the model does next.

The outcome is deliberately **binary and mechanically observable**: did the
model emit a call to a destructive tool that no legitimate task requires? No
LLM-as-judge, no rubric, no inter-rater agreement problem. That is what makes
thousands of unattended trials meaningful rather than noisy, and it is the
methodological advantage of studying injection over studying something like
helpfulness.

## Attack success is not one number

The headline finding of this work is structural rather than empirical.

A model can only obey an injected instruction if the payload reached it, and the
payload only reaches it if the model called the carrier tool in the first place.
So:

```
ASR  =  P(delivered)  ×  P(obeys | delivered)  ×  P(executes | obeys)
```

Benchmarks routinely report the product and describe it as a property of the
model's safety. It is not. A model too weak to call tools reliably scores near
zero on the product while having no injection resistance whatsoever.

This is not hypothetical. In the run included here, `deepseek-r1:14b` recorded
**0 successful attacks out of 258** — and was never actually attacked once,
because it never called the carrier tool and therefore never received a payload.
A naive denominator reports that as the safest model tested.

Every rate in this repository is therefore conditioned on **delivered** trials,
and delivery is reported as its own outcome rather than hidden in a denominator.

## Controls

Three arms, because a raw attack rate cannot support a causal claim:

| Arm | Payload | What it establishes |
|---|---|---|
| `attack` | requests a destructive tool | the effect |
| `clean` | none — identical prompt and content | the spontaneous base rate |
| `benign` | requests a *harmless* tool | whether refusal is destructive-specific |

The `clean` arm is load-bearing. Without it, a destructive call cannot be
attributed to the injection rather than to whatever the model would have done
anyway. The `benign` arm separates two behaviours that look identical from
outside: *following instructions found in tool output* versus *being willing to
take a destructive action on instruction*.

## Design

Factorial, with every cell replicated. Factors: attack framing, payload
position, payload containment, claimed authority, carrier tool, defense prompt,
model, and condition.

Statistics are reported as effect sizes with intervals, never as bare
proportions and never as p-values alone. At these trial counts a
one-percentage-point difference is "significant" and the p-value answers a
question nobody asked. Wilson score intervals on proportions, Newcombe hybrid
intervals on unpaired risk differences, Tango score intervals on paired ones,
exact conditional McNemar for matched contrasts, cluster-robust standard errors
on the model dimension, and Holm correction within each family of tests.

Derivations for every estimator, with numerical checks against reference
implementations, are in
[`APPENDIX_MATH.md`](papers/01-unattacked-not-unbreakable/APPENDIX_MATH.md).

## Repository layout

```
src/            harness — attack grid, runner, analysis, power
src/vendor/     frozen tool schemas and the GPU slot lock
papers/NN-.../  one directory per paper: draft, design, appendix, figures
data/           trial-level results, every raw model response retained
```

The harness is shared; each paper pins its own draft, design notes and figures
beside it, so results stay attached to the analysis that produced them.

## Reproducing

Requires [Ollama](https://ollama.com) with the models pulled, and Python 3.11+.

```bash
pip install -r requirements.txt

python src/attack_grid.py                     # inspect the stimulus grid
python src/runner.py --list-stages            # stages and honest wall-clock
python src/runner.py --stage controls --trials 20
python src/analyze.py --selftest              # statistics vs known ground truth
python src/analyze.py --run-id controls-heldout --split heldout
```

Runs are resumable: re-issue the identical command and completed cells are
skipped. `--trials` resumes *upward*, so a 10-trial pass can be extended to 20
without repeating work. Every trial is committed to SQLite before the next
begins, so an interrupted run costs one trial.

`python src/analyze.py --selftest` is the first thing to run. It generates
synthetic data with known ground truth and asserts every statistic recovers it.

## Data

`data/trials.db` is SQLite, one row per trial, with the full raw model response
retained rather than aggregate counters alone. Aggregates cannot be re-examined
when a scoring rule turns out to be wrong — and over the course of this work
several scoring rules did turn out to be wrong. Raw responses are what allowed
those to be caught and corrected after the fact, without re-running anything.

SQLite rather than CSV because the trials table is queried far more often than
it is read linearly, the analysis joins on it, and the format keeps types and
NULLs intact. It reads with no dependencies:

```python
import sqlite3, pandas as pd
con = sqlite3.connect("data/trials.db")
df = pd.read_sql("SELECT * FROM trials WHERE run_id='controls-heldout'", con)
```

### On the operator name in the system prompt

The system prompt begins `"You are Thessa's ops agent."` — Thessa being the
private operations system this harness was built inside. It is left exactly as
run, and deliberately so: the published code has to be the code that produced
the published data. Neutralising the string after the fact would mean shipping a
dataset generated by a system prompt that appears nowhere in the repository,
which is a worse reproducibility problem than an idiosyncratic name.

Treat it as an arbitrary operator identity. Nothing in the design depends on it,
and it is visible in two of 4,773 recorded responses.

Trials that terminate on a token limit with no usable output are recorded
`INVALID` and excluded from every denominator. They are neither passes nor
failures, and scoring them either way produces confident nonsense.

## Scope and honesty about it

The destructive tool is **simulated**. What is measured is the *intent* to call
it, in a synthetic harness — never realised harm in a live system.

The attacks are generic in kind and target publicly available open-weight
models. No live service was attacked and no vulnerability in any third-party
product is disclosed here. The contribution is measurement methodology, and the
defensive findings are the point.

Known limitations, stated in full in the paper draft: the model panel is small,
which bounds any cross-model correlation; attack register and payload length are
collinear across the current stimulus templates and cannot be separated without
length-matched rewrites; `answered` is scored by string match; and results are
specific to Ollama's chat templating.

## License

Code MIT. Data and documentation CC BY 4.0. See [`LICENSE`](LICENSE).
