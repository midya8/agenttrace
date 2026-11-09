# AgentTrace graph/timing evidence

## Meaning before arithmetic

The inspector accepts supplied records. It does not run an agent, authenticate a trace, synchronize clocks, establish complete instrumentation or measure resource utilization. The original example traces are fixed synthetic data. Their cost/token/time fields are not claims about any real model. AgentTrace is not an OpenTelemetry-compatible collector or production observability system.

A parent field supplies hierarchy/context, not a finish-to-start dependency. Forward references are valid once all ids resolve; unknown/cyclic/duplicate ids invalidate the graph. Depth counts a root as one. Topological order uses lexical roots and children in a breadth-first queue. Every root-to-node path and duration sum is retained; this sum may count nested/overlapping time repeatedly. It is not a causal critical path, execution makespan, self time or exclusive duration. A child outside its parent's time range is a recorded relation, not automatic proof of corruption: async work, instrumentation and clocks require separate investigation.

## Interval contract

For each timestamped event, start_ms is the exact UTC epoch-millisecond conversion and end=start+duration. Positive-duration intervals are half-open [start,end). Group tied boundaries; remove endings, add starts, then expose the active ids for the next interval. Zero-duration records are points and change no active set. Every endpoint and every between-endpoint segment, including gaps, remains in the export.

- Step-duration sum includes untimed events.
- Timed-duration sum includes only events with timestamps.
- Recorded span is maximum timed end minus minimum timed start, including zero-duration points. With no timestamped events it is undefined/null, not zero. A single point has span zero.
- Busy union is the sum of segment widths with any active span. It is recorded coverage, not measured CPU busy time.
- Weighted area is sum(width × active count) and equals timed-duration sum for the bounded integer contract.
- Overlap excess=weighted area-busy union. It is repeated accounting, not wasted work.
- Uncovered span=recorded span-busy union. It is not proof of idle time or absent work.
- Peak recorded spans is maximum active count over positive-width segments. It is not core/worker utilization. Adjacent end/start events do not create a spurious overlap.

Missing timestamps remain unknown, never become time zero. Partial coverage is explicitly marked. Distinct runs are analyzed separately and are not merged into one wall-clock timeline. Shared clock agreement, completeness and correct instrumentation are not established here. No skew correction, bottleneck diagnosis or latency prediction is attempted.

P95 preserves the original linear interpolation: sorted durations, rank=(n-1)*.95, low=floor(rank), high=min(low+1,n-1), weight=rank-low. Every term and sorted row is exported. All durations, including zero/untimed steps, enter this step-duration percentile. No run means no percentile report. This is not nearest rank, uncertainty or an elapsed-run percentile. Different conventions are not silently treated as equal.

## Native corrections and retained work

Original parser accepted nonfinite known numbers and JSON constants, mixed missing/present timestamps could crash sorting, cycles produced recursive/order-dependent depth, and analysis JSON ok ignored parser issues. The parser now flags duplicate JSON keys and nonfinite JSON tokens/known numeric fields, graph analysis is iterative, mixed timestamp sorting is explicit and invalid graph/parser status propagates to JSON/comparison gates. Unknown native event fields remain outside the typed analysis, so native loading is not a lossless arbitrary-schema archive. Raw source traces should be retained separately. Native input/output values are supplied data, not authorized instructions.

Comparison percentage change from zero is undefined/null, replacing nonstandard Infinity JSON. Positive increase still fails a configured percent bound. Gate defaults and valid-trace metrics are preserved; analysis/compare CLI choices are not inferred from the inspector. Invalid numeric gate options fail rather than silently disabling checks. Native input validation is not a direct-TraceStep object sanitizer.

`docs/original-sha256.json` fingerprints original33tests, baseline/candidate JSONL, demo and README. README is archived as original-readme.md. The original baseline source, original CLI analysis and original HTML remain visible and are reproduced by the updated analyzer/renderer on the original valid fixture. The original demo remains unchanged. No outputs are represented as a new model/adapter run.

## Bounded inspector schema

Exactly one root field events, <=16 event objects and <=4 runs. Only the existing event fields run_id/step/parent/kind/name/status/started_at/duration_ms/tokens_input/tokens_output/cost_usd/input/output are allowed; unknown fields are rejected rather than silently discarded. Required ids/name are nonblank printable ASCII <=64 characters, parent is null/omitted or a nonblank id. Valid original kinds/statuses apply. Durations are integer milliseconds 0..1,000,000; tokens integers 0..1,000,000; cost in [0,1] on a micro-dollar grid (absolute scaled tolerance1e-8). UTC timestamps are YYYY-MM-DDTHH:MM:SSZ or three-digit .sssZ, years2000..2100 with actual calendar validation. Native ISO parsing is broader.

Payloads are null/Boolean, integer magnitude<=1,000,000, bounded printable ASCII strings<=512, arrays/objects<=16 items at each level and depth<=4. Object keys<=64. Text permits tab/newline/CR. Payload numbers are integers, avoiding cross-language decimal signature ambiguity. Audit files <=128KiB reject duplicate keys and nonfinite tokens; UI JSON parsers do not claim duplicate-key detection. Source spec is retained alongside complete normalized records, source sequence and converted start_ms. Unknown timestamps stay null. Export is the recomputed current report, never a retained default disguised as current output.

## Independent verification

All 11,110 interval lists of lengths1..4 from the ten nonnegative intervals on endpoints0..3 (including zero intervals) are compared to separate unit-cell counting: union, peak, weighted sum and span. Full retained controls cover original data, nested spans, touching endpoints, gaps, zero points, mixed/all-missing timestamps, forward parent order, noncontained children, multiple roots/runs, p95 ties/interpolation, errors, escaped payloads and maximal chains/concurrency. A 5,000-deep native graph verifies no recursion dependence.

All 24 full reports match an independent scalar JavaScript implementation at 2,060 numeric/2,463 other leaves. Actual Chrome reads every run's endpoint/segment/path/relation/p95 table and complete record, checks every timeline mark's id/data/position, summary quantities, stale-state/export and 320/390/1280 containment. No image replaces computed evidence. Isolated installed-wheel checks run outside the checkout, verify eleven module origins and all reports, then exercise all CLI modes and JSON/HTML/JUnit/Markdown/SARIF reports. CI runs Python3.10-3.13 and actual Chrome. Same-environment regeneration is not an all-platform determinism promise.

## Sources and prior work

Parent spans, interval sweeps and linear quantiles are established. This work contributes complete graph/timing witnesses, native integrity fixes, bounded independent recomputation and displayed-record/export verification, not a new tracing or scheduling theory. No external code or trace data copied.

- [OpenTelemetry traces](https://opentelemetry.io/docs/concepts/signals/traces/): parent context, timestamps and hierarchy; producer/consumer processing may start after a producer ends.
- [OpenTelemetry API specification](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/trace/api.md): timestamps, span boundaries and parent context. Ending a span is not a scheduler for children.
- [NumPy quantile](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html): linear/Hyndman-Fan7 rank=(n-1)*q interpolation. The original AgentTrace convention is preserved, without a NumPy dependency.
- [Interval union community discussion](https://stackoverflow.com/questions/1034802/union-of-intervals): sorted endpoints/sweep-line prior art.
- [Sweep-line explanation](https://dsa.handbook.academy/patterns/sweep-line-archetypes/): active sets change at endpoints and are constant between them.
- [Jaeger clock precision issue](https://github.com/jaegertracing/jaeger-client-java/issues/192): clock/start-time precision and duration measurement can create misleading span relations. Historical implementation discussion, not a claim about all current SDKs.

Read November8,2026. These sources support definitions/cautions, not evidence that synthetic traces reflect real application behavior.
