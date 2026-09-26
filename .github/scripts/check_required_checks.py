#!/usr/bin/env python3
"""Fail when .github/rulesets/main.json names a check no workflow reports, or stops gating main.

``.github/rulesets/main.json`` is the ruleset that protects main, as GitHub exports it and in
the form its "Import a ruleset" takes -- the checks a pull request has to pass before it merges,
and the rest of what GitHub enforces there -- so that what gates a merge can be read and diffed
rather than believed. It is also what ``.github/workflows/dependabot-auto-merge.yml`` relies on:
"gh pr merge --auto" waits for exactly the checks the ruleset requires, and for nothing at all
when it requires none.

GitHub matches a required check by the job's display ``name:`` -- never the workflow's name,
never the job's key -- so renaming a job without editing this file leaves a context that no run
will ever report. On this repository, where GitHub enforces the ruleset, that blocks every pull
request, Dependabot's included, until someone with admin rights notices. Nothing about it looks
broken from the pull request: the check just says "Expected -- Waiting for status to be
reported", forever.

wader/postfix-relay keeps its own copy of such a file true with ``tests/test_ruleset.py``; this
is the same two checks, written with the standard library alone, because this repository has no
test suite and its CI installs nothing.

What is checked
---------------

* Every ``context`` in the one ``required_status_checks`` rule is the display name of a job in
  ``.github/workflows/*.yml`` -- its ``name:``, or its key when it has none, which is the name
  GitHub reports it under.
* The file still gates the default branch: exactly one ``required_status_checks`` rule, with at
  least one check in it; enforcement ``active``, targeting ``~DEFAULT_BRANCH`` with nothing
  excluded, and no bypass actor. A re-export made after clicking around the settings page can
  bring any of those back while the file still parses.
* No ``pull_request`` rule requires an approval. One required approval would hold every
  Dependabot update for a person however green its checks are, and "gh pr merge --auto" would
  wait for that approval as patiently as it waits for the checks.

Any other rule is neither required nor refused. The live ruleset carries more than the checks --
``deletion``, ``non_fast_forward`` and ``required_linear_history`` among them today -- and
the file records it whole, so that importing it in place of the live one drops nothing. Refusing
those rules would stop the file from saying what GitHub enforces; requiring them would turn every
change to the ruleset into a red build here, for no defect this check exists to catch.

What is deliberately *not* checked
-----------------------------------

Whether a required job actually *runs* on a pull request. A job that reports only on version
tags -- the Docker image job here -- passes this check and then never reports on a pull request;
that is a decision about which jobs belong in the list, and it is made where the list is edited,
not guessed at here.

Whether the file is what GitHub enforces. The live ruleset is a setting, edited in the settings
page, and nothing in the tree can see it change; the file differed from it the day both were
made. Re-export it after editing the ruleset, and read the diff.

Whether the merge method in ``dependabot-auto-merge.yml`` is one the ruleset lets through. That
is stated beside the ``gh pr merge`` call instead: ``required_linear_history`` refuses a merge
commit, which is why the call squashes.

The workflows are read with a line scanner rather than a YAML parser, because the standard
library has none and this runs on the runner's own python3 without installing anything. It only
has to find two things -- the two-space job keys under the top-level ``jobs:`` and the
four-space ``name:`` directly beneath each -- and every workflow in this repository is written in
that shape. A job this scanner cannot see is reported as missing, so the failure mode of the
shortcut is a false red, never a false green.

Run it by hand from the repository root:

    python3 .github/scripts/check_required_checks.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULESET = ROOT / ".github" / "rulesets" / "main.json"
WORKFLOWS = ROOT / ".github" / "workflows"

JOB_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$")
JOB_NAME = re.compile(r"^    name:\s*(.+?)\s*$")


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def reported_names() -> dict[str, str]:
    """Every check name a workflow can report, mapped to the file reporting it."""
    names: dict[str, str] = {}
    workflows = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    for workflow in workflows:
        in_jobs = False
        key: str | None = None
        named = False
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if line.startswith("jobs:"):
                in_jobs = True
                continue
            if not in_jobs:
                continue
            if line and not line.startswith(" ") and not line.startswith("#"):
                in_jobs = False
                continue
            if match := JOB_KEY.match(line):
                if key is not None and not named:
                    names[key] = workflow.name
                key, named = match.group(1), False
                continue
            if key is not None and not named and (match := JOB_NAME.match(line)):
                names[unquote(match.group(1))] = workflow.name
                named = True
        if key is not None and not named:
            names[key] = workflow.name
    return names


def main() -> int:
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))
    problems: list[str] = []

    if ruleset.get("target") != "branch":
        problems.append(f'"target" is {ruleset.get("target")!r}, expected "branch".')
    if ruleset.get("enforcement") != "active":
        problems.append(f'"enforcement" is {ruleset.get("enforcement")!r}, expected "active".')
    ref_name = ruleset.get("conditions", {}).get("ref_name", {})
    if ref_name.get("include") != ["~DEFAULT_BRANCH"] or ref_name.get("exclude") != []:
        problems.append(
            f"it targets {ref_name!r}, expected the default branch and nothing excluded."
        )
    if ruleset.get("bypass_actors") != []:
        problems.append(f'"bypass_actors" is {ruleset.get("bypass_actors")!r}, expected none.')
    rules = ruleset.get("rules", [])
    status_rules = [rule for rule in rules if rule.get("type") == "required_status_checks"]
    contexts: list[str] = []
    if len(status_rules) != 1:
        problems.append(
            f"it carries {len(status_rules)} required_status_checks rules, expected exactly one."
        )
    else:
        parameters = status_rules[0].get("parameters", {})
        checks = parameters.get("required_status_checks", [])
        contexts = [check.get("context", "") for check in checks]
        if not contexts:
            problems.append(
                "it requires no check at all, so auto-merge would merge before CI said anything."
            )
    approvals = sum(
        rule.get("parameters", {}).get("required_approving_review_count") or 0
        for rule in rules
        if rule.get("type") == "pull_request"
    )
    if approvals:
        problems.append(
            f"its pull_request rule requires {approvals} approval(s), which would hold every "
            "Dependabot update for a person however green its checks are."
        )

    reported = reported_names()
    if not reported:
        problems.append(
            f"no job was found under {WORKFLOWS.relative_to(ROOT)} -- have the workflows moved?"
        )
    for context in contexts:
        if context not in reported:
            problems.append(f'required context "{context}" names no job, so it can never report.')

    if problems:
        print(f"{RULESET.relative_to(ROOT)} no longer describes a gate that can pass:")
        for problem in problems:
            print(f"  - {problem}")
        print()
        print("Job names that do report: " + ", ".join(f'"{name}"' for name in sorted(reported)))
        return 1

    print(
        f"{len(contexts)} required check(s), each reported by a job: "
        + ", ".join(f'"{context}" ({reported[context]})' for context in contexts)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
