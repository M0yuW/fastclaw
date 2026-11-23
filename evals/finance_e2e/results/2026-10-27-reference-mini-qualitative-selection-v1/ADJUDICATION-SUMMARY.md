# Response-blind four-observation diagnostic review

Selection was frozen before these four answers were read. `SELECTION.json` records the fixed hash ranking of four previously blank score templates from 50 eligible observations, with four distinct issuers. `MANIFEST.json` binds the selection to the archived 150-result hash list, masked-packet hash list, private mapping and selection script. The original result and score-template files were not modified. The four authored reviews live separately in `reviews/` and pass the repository's `validate_review` rubric checker.

| Masked observation | Issuer after unmasking | Local diagnostic label | Material finding |
| --- | --- | --- | --- |
| `J-b6e559adea6c6abb` | BOKF | problematic | Saved rationale assures a research hold, but the ledger remains `decision_hold=false` and `actionability=available`; final structured state itself accurately says available. |
| `J-d9ea0e54a3a5b5f4` | EFX | problematic | Both final answer and stored rationale reverse the signed tax-provision change. A USD 14.9 million tax offset to the pretax decline is described as a larger tax drag. The ledger is correctly blocked. |
| `J-c710f1dc5f64baef` | SSB | adequate | Correctly separates stronger earnings from weaker credit indicators and leaves the ledger blocked, but overinterprets the earlier reported-versus-adjusted charge-off ratio gap. |
| `J-bf4eba69527e01ab` | TOST | problematic | Both final answer and stored rationale reverse the signed tax line: `-3` to `+1` USD million contributes `+4`, rather than offsetting the `+21` pretax change. The ledger matches the asserted available state. |

Result: zero high, one adequate, three problematic **among these four selected observations only**. This is not a quality rate for the 150-run panel. The selection was response-blind but not an issuer-level holdout: other answers for the same issuers had been seen previously, and Codex is not an independent financial expert. The no-high result is a useful stress test of the claim that illustrative successes imply reliability. It does not erase the separately documented, source-bounded high-quality examples (notably MQ), nor does it license presenting those examples as representative.

The engineering findings are separable. BOKF is a prose-versus-ledger state-consistency defect that a deterministic precommit/state-assertion check could address. EFX and TOST expose financial sign and bridge errors in generated interpretation; their correct or mechanically complete ledger workflows do not make the analysis correct. SSB is mainly an inference-boundary issue, not a tool-execution failure. A controlled development A/B should target the specific guardable errors and preserve failures in the denominator, rather than change the scoring rules after seeing results.

Review file SHA-256 values at this adjudication version:

```text
549796cdf0efe030cf40080d3702a18b7fbb7f23125b6317ab8b3e7b5a5751b7  reviews/J-b6e559adea6c6abb.json
7702dcfbc11f759cbaccf890154d6bca0242238bccd13e5220e0d8e19586fe89  reviews/J-bf4eba69527e01ab.json
5d172c1455965c65b4c222f3b2910182c0bbcb34d7779a4295813f44bd82c8ae  reviews/J-c710f1dc5f64baef.json
0df1cb83b683d7a21e3c6333208ca8ab8a7d63b2b12b07d72cf0c07fef9960e4  reviews/J-d9ea0e54a3a5b5f4.json
```
