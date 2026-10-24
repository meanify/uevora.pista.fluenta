---
tags: [skill-creator]
max_turns: 80
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

I need a new INE flow for indicator 9875 (capacidade de alojamento) loading into
ine_0009875 — DDL is in ine_0009875.sql. The INE API is blocked from this machine, so
use the saved responses instead: metadata is meta_0009875.json and the 2024 data
request (op=2, Dim1=S7A2024) response is data_0009875_2024.json. Add it to the CLI with
tests and update the README.

Input files: ine_0009875.sql, meta_0009875.json, data_0009875_2024.json
