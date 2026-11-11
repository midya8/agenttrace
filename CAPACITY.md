# Fixed-interval retention policy

AgentTrace 0.2 adds a separate exact policy experiment: retain a maximum-value subset of supplied fixed intervals under a declared overlap cap. Equivalently, minimize the sum of supplied penalties for dropped intervals. No trace records are deleted. The original validator, analyzer, compare/report commands, timing audit, gates and original fixtures are unchanged.

[Open the policy inspector](https://midya8.github.io/agenttrace/capacity.html). [Original timing inspector](https://midya8.github.io/agenttrace/).

## A long span is not always worth keeping

The default synthetic input has `[0,4)` with drop penalty 9, `[0,2)` with penalty 6 and `[2,4)` with penalty 6. With cap 1, retaining the two touching shorter intervals keeps penalty 12 and drops penalty 9. Keeping the single largest-penalty interval would keep only 9. With cap 2, all three fit and dropped penalty is 0. Cap 0 drops every positive-duration interval.

This is not a measured agent run or a recommendation to cancel real work. Penalties are supplied priorities, not measured model quality, monetary charges or causal effects. Recorded parent spans may enclose child spans; treating those spans as one-unit tasks is a new policy assumption, never inferred from the original trace.

## Exact input and semantics

Input has exactly `capacity` and `intervals`. Each interval has exactly `id`, `start`, `end`, `drop_penalty`.

- At most 12 intervals. Capacity is an integer in 0..4. Start/end are integers in 0..1,000,000, with end >= start. Penalties are integers in 0..1,000. Numbers have no inferred time unit.
- IDs are unique ASCII labels: a letter followed by letters/digits/underscore/hyphen, at most 24 characters. Input order fixes the tie rule, not chronological order.
- Every selected positive-duration interval consumes one hypothetical lane throughout the half-open interval `[start,end)`. Touching intervals can share a lane. No preemption, movement of endpoints, release/deadline windows, precedence, variable resource demand, machine eligibility or multiple alternative intervals per job.
- A zero-length interval is an empty interval/point and consumes no capacity by explicit convention. Positive-penalty points are retained even at cap 0; zero-penalty points are dropped by the tie rule. This does not mean an instrumented point event costs no real resources.
- Unknown/missing timing is rejected. There is no certification of an incomplete trace's true capacity. This separate schema does not auto-convert trace events, infer run clocks or interpret parent relationships as dependencies.
- Primary objective: maximize retained penalty, hence minimize dropped penalty. Secondary objective: smallest retained bitmask in supplied input order. Bit i is 1 if interval i is kept. This is a deterministic, order-dependent choice among primary optima, not a ranking of equal-value plans or enumeration of all primary optima.
- Empty input has zero dropped penalty, no segments and an empty network. A point-only input similarly has no network but may retain point penalties.
- Browser/CLI JSON rejects duplicate keys, decimals/exponent/negative numeric spellings, nonfinite numbers, >128 KiB input and nesting deeper than 8. Object APIs require actual integer values, not booleans or floats; lexical spelling is a JSON boundary concern.

## Actual native solver

Let n be the number of all input intervals and `B = 2^n`. Each positive-duration interval i gets composite benefit `penalty_i * B - 2^i`. The secondary mask difference between any two subsets has absolute value less than B, so one integer unit of primary retained penalty always dominates every secondary tie difference. A zero-penalty interval has negative benefit and is never useful.

Make one vertex per distinct start/end of a positive-duration interval, in time order. Add an idle arc from each time to the next with capacity k and cost 0. Add each interval's start-to-end arc with capacity 1 and cost negative composite benefit. Parallel original arcs are distinct. Send k units from first to last time at minimum cost. Every integral path is one hypothetical lane, so the chosen event arcs give a feasible retention set, and every feasible lane assignment gives such a flow. Idle arcs guarantee feasibility for any cap, including cap 0. Points are handled separately rather than inserted as negative-cost self loops.

Python implements successive shortest paths in the actual residual network. It uses Bellman-Ford on raw costs, including negative interval/reverse costs, not Dijkstra with invalid initial costs. Forward and reverse residual arcs retain their original edge index and direction. Integer capacities and unit path augmentations produce integral flows. The inspector exposes the final complete network, not just an objective value. It does not claim a new algorithm, scalable implementation, runtime benchmark or memory advantage.

All capacities 0..4 are solved. The report includes that complete objective/retained-set frontier; the selected capacity additionally includes the full network certificate. Feasible lanes are greedily assigned to the retained intervals ordered by start, then end, then original index, choosing the first available lane. Those lane numbers are a witness, not part of the optimization objective or observed worker identity.

## Check the optimum certificate

After solving, super-source shortest distances with zero starting distance at every vertex give potentials p. For each residual arc u->v, the reduced cost is `cost + p[u] - p[v]`. Every residual reduced cost is nonnegative. Potentials have the canonical shortest-distance normalization from that zero-cost super source, rather than an arbitrary additive shift.

The full report retains every original edge/capacity/cost/flow, each residual direction/capacity/cost/reduced cost, every time vertex/potential, flow value, composite primal cost, dual bound and exact gap. For the positive-duration network:

```
primal = sum_e flow_e * cost_e
reduced_e = cost_e + p[from_e] - p[to_e]
dual = k * (p[last] - p[first])
       + sum_e capacity_e * min(0, reduced_e)
```

Primal equals dual and the gap is exactly zero. Together with capacity bounds and flow conservation this certifies the declared network optimum. Nonnegative residual costs rule out a cheaper cycle; the dual is a matching lower bound. It is an integer arithmetic certificate, not a formal proof-assistant artifact. Positive-penalty point benefits and their tie bits are outside this network; they are fixed optimal additions and are included in the reported retained mask and retained/dropped penalties, not misreported as network edge costs.

The browser deliberately uses a different optimizer: enumerate every subset, evaluate load on all adjacent endpoint midpoints, select primary penalty then smallest mask, reconstruct chosen interval flows and idle flows, and compute canonical potentials using Floyd-Warshall all-pairs distances. Full reports agree, including every residual arc and exact potential, not only kept IDs. At most 12 rows means 4,096 subsets. This is a bounded independent reference, not a browser min-cost-flow speed claim.

## Reproduce

```sh
python -m unittest discover -s tests -v
python tools/build_capacity.py
python -m agenttrace.capacity_cli --input examples/capacity.json > /tmp/capacity-report.json
python -m pip install .
agenttrace-capacity --input examples/capacity.json
npm test
bash tools/wheel_smoke.sh
bash tools/capacity_wheel_smoke.sh
```

```python
from agenttrace import capacity_report
r = capacity_report({'capacity': 1, 'intervals': [
    {'id': 'long', 'start': 0, 'end': 4, 'drop_penalty': 9},
    {'id': 'left', 'start': 0, 'end': 2, 'drop_penalty': 6},
    {'id': 'right', 'start': 2, 'end': 4, 'drop_penalty': 6},
]})
assert r['selected']['retained_ids'] == ['left', 'right']
assert r['selected']['drop_penalty'] == 9
assert r['selected']['network']['gap'] == 0
```

64 Python tests retain all 57 earlier tests. An independent original-row unit-cell/full-subset oracle checks 250 seeded cases at all five capacities; 120 larger endpoint/penalty cases check primal/dual, capacities, conservation, residual signs and lane feasibility. Dedicated controls cover touching endpoints, point spans, zero capacity/penalties, empty input, parallel identical intervals, nested spans, input-order ties and maximum bounds.

Seven Node/actual-Chrome tests retain all three earlier tests. Native and independent browser agree on all 24 complete reports, 113 interval rows, 124 segments, 120 frontier entries, 222 original network edges and 241 residual arcs. Chrome checks every displayed row, all timeline geometry and point marks, invalid/stale state, 320/390/1280 containment and both exports. Actual trusted clicks save input/report files and replay downloaded input through native CLI. An isolated installation outside the checkout checks separate API, module and console on every report; the original eleven-module wheel plus validate/analyze/report/compare/audit and original report outputs still pass.

## Sources and scope

Original implementation and synthetic fixtures, no external code/data copied. The fixed-interval min-cost-flow method is established work, not a new algorithm.

- [Arkin and Silverberg, Scheduling jobs with fixed start and end times (1987)](https://doi.org/10.1016/0166-218x(87)90037-0): historical fixed-interval scheduling method.
- [Borodin, University of Toronto CSC2420 Lecture 6 (2012)](http://www.cs.toronto.edu/~bor/2420f12/L6.pdf): weighted m-machine interval scheduling to min-cost flow; negative-cycle reasoning.
- [Kolen et al., Interval Scheduling: A Survey](https://ir.cwi.nl/pub/11585/11585B.pdf): fixed intervals, weighted identical-machine selection, distinctions from richer models.
- [k-machine interval scheduling reference](https://algorithm.tamnd.com/k-machine-interval-scheduling/): endpoint-network reduction and endpoint convention.
- [Furini, reduced-cost optimality conditions](https://fabiofurini.github.io/network-optimization/flows/min-cost-flow/optimality-conditions-with-potentials/): residual potentials and nonnegative reduced costs.
- [Furini, successive shortest paths](https://fabiofurini.github.io/network-optimization/flows/min-cost-flow/the-successive-shortest-path-algorithm/): residual directions and shortest-path/potential signs.
- [Zeh, Dalhousie Algorithms II, complementary slackness](https://web.cs.dal.ca/%7Enzeh/Teaching/4113/book/mincostflow/characterization/slackness.html): capacitated primal/dual and complementary slackness.
- [Google OR-Tools minimum-cost flow documentation](https://developers.google.com/optimization/flow/mincostflow): supply, conservation, capacity and cost definitions. OR-Tools is not a dependency.
- [CP Algorithms minimum-cost flow](https://cp-algorithms.com/graph/min_cost_flow.html): reverse arcs and parallel-edge caution.

A separately reviewed weighted job-interval-selection paper allows multiple alternative intervals per job and studies approximation. That is a different problem and its hardness/approximation results are not claimed for this one-fixed-interval audit. Neither a supplied drop penalty nor a certified chosen subset establishes real savings, quality, dependency-safe cancellation, true worker use or counterfactual run duration.
