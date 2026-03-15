---
title: "Skill Audit Remediation Guide"
tags: [skills, security, remediation]
scope: dev
---

# Remediation Guide

## Hardcoded Credentials

- move secrets to environment variables
- remove committed tokens from examples and tests
- rotate any real secrets that were previously committed

## Undeclared Network Access

- document remote access clearly in `SKILL.md`
- add `url` inputs or explicit network wording where appropriate
- if remote access is not required, remove the code path

## IO Overreach

- declare file outputs in `io.output`
- keep temporary files inside a documented workspace path
- avoid writing outside the intended skill boundary

## Risky Reverse API Flows

- rename the skill to include a clear risk marker such as `danger-`
- explain user consent and operational risks in `SKILL.md`
- document fallback paths that use official APIs when possible
