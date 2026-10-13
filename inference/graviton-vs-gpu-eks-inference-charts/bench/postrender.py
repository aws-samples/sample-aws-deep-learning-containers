#!/usr/bin/env python3
"""helm --post-renderer for benchmark-charts (ai-on-eks-charts commit 21fda29). Known chart issues 5 and 6 (see README).
The chart's configmap only supports rate-based stages, data.type synthetic and S3 storage, so
replace config.yml with $BENCH_CONFIG verbatim and make the job print the JSON reports to stdout."""
import os, sys, yaml
docs = [d for d in yaml.safe_load_all(sys.stdin) if d]
cfg = open(os.environ["BENCH_CONFIG"]).read()
run = ("inference-perf --config_file /workspace/config.yml; rc=$?; "
       "for f in /tmp/reports/*.json; do echo \"=====BEGIN $f\"; cat $f; echo; echo \"=====END $f\"; done; exit $rc")
for d in docs:
    if d.get("kind") == "ConfigMap":
        d["data"]["config.yml"] = cfg
    if d.get("kind") == "Job":
        c = d["spec"]["template"]["spec"]["containers"][0]
        c["args"] = [run]
        d["spec"]["backoffLimit"] = 0
yaml.safe_dump_all(docs, sys.stdout, sort_keys=False)
