# Citation-development protocol v2

This is a **seen-case, prompt-and-gate development run**, not an independent
test of financial insight quality. FITB, RELY, TFC, and VRSK reuse the frozen,
previously observed SEC row packets; each has two fresh, isolated DeepSeek
Flash Gateway sessions. The run order is deterministic and recorded by hash.

The model is asked to select host-verified sequential comparison IDs for
support and counterevidence, make a bounded qualitative interpretation, save
one version-protected source-linked thesis review, acknowledge the alert, and
report actual ledger state. The complete comparison table remains visible.
The final candidate is checked by the pre-existing mechanical gate plus the
conservative semantic red-flag screen added after v1. These checks can **hold**
an answer; absence of a flag is not a financial-quality pass. Every answer
still requires claim-level source and interpretation review.

The user authorized this batch alone with a new USD 0.25 cumulative **estimated**
cost ceiling. The harness reserves USD 0.05 before each next observation and
stops on a request error, uncertain/unpriced cost, or exceeded cap. Failures
are retained and not retried. The Gateway uses isolated copied configuration
and ledger databases, not the running user service. No v1 result is replaced
or pooled with this run.

The first attempt, TFC repetition 1, stopped before any model turn because
the sandbox prevented the isolated Gateway from finishing startup. Its failed
observation and zero estimated cost are retained in the initial v2 result
directory. A separate free scripted Gateway smoke test passed outside that
sandbox with zero provider requests. Only the seven **unattempted** IDs may
continue in a separate result directory under the same USD 0.25 ceiling; the
failed ID must not be retried or counted as a successful session.
