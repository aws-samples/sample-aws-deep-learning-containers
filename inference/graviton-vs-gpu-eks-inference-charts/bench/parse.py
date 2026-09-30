#!/usr/bin/env python3
"""Usage: parse.py results/<release>/job.log. Prints a markdown table with one row per inference-perf stage."""
import re, json, sys
s = open(sys.argv[1]).read()
print("| Stage | Load | OK/fail | TTFT p50 (s) | ITL p50 (ms) | Per-user t/s | Output TPS | Req lat p50 (s) |")
print("|---|---|---|---|---|---|---|---|")
for m in re.finditer(r'=====BEGIN \S+stage_(\d+)_lifecycle_metrics.json\n(.*?)\n=====END', s, re.S):
    d = json.loads(m.group(2)); ls = d["load_summary"]; ok = d["successes"]; lat = ok.get("latency") or {}
    load = f"conc {ls['concurrency']}" if ls.get("concurrency") else f"rate {ls['requested_rate']} (got {ls['achieved_rate']:.1f})"
    g = lambda k: (lat.get(k) or {}).get("median")
    itl = g("inter_token_latency")
    f = lambda v, n=2: "n/a" if v is None else f"{v:.{n}f}"
    print(f"| {m.group(1)} | {load} | {ok['count']}/{d['failures']['count']} | {f(g('time_to_first_token'))} | {f(itl*1000 if itl else None,1)} | {f(1/itl if itl else None,1)} | {f(ok['throughput']['output_tokens_per_sec'],1)} | {f(g('request_latency'))} |")
