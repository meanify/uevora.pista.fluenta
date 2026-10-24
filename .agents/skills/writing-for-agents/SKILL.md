---
name: writing-for-agents
description: "Write or revise concise agent-facing instructions, navigation guides, review criteria, and skills. Use when a retrospective proposes environment improvements or agent documentation is being edited."
---

# Writing for agents

- Lead with the action and when it applies. State the scope and observable
  outcome rather than offering generic advice.
- Keep always-loaded instructions short. Link to existing documentation for
  setup, architecture, and detailed workflows.
- Give paths and commands relative to an explicit working directory. Do not
  assume a previous shell call changed the current directory.
- Put mechanical requirements in automated checks when practical. Put genuine
  judgement calls in reviewer criteria, with examples of what to compare.
- Avoid duplicate rules, speculative abstractions, and repeated approval gates.
  Usage questions need answers; an agreed behavior-preserving refactor needs
  implementation and tests, not a new feature-design process.
- Use only available skills and tools. If a local skill is not yet discoverable,
  read its source; do not invent commands or require an unrelated installation.
- Preserve credentials and other private information. Examples must use
  placeholders, never actual secret values.
- Validate referenced paths, commands, and skill frontmatter before reporting
  completion. Distinguish locally verified behavior from external activation.
