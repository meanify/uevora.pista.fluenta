---
name: brainstorming
description: "Explore unresolved requirements and design choices for new features or intentional behavior changes. Use for open-ended design requests; not for usage questions, code explanations, bug fixes with clear expected behavior, or agreed behavior-preserving refactors."
---

# Focused design discussion

1. Inspect the relevant existing code and documentation before asking questions.
   Answer a usage question directly when existing behavior already resolves it.
2. Identify decisions that materially affect scope or behavior. If none remain,
   implement the explicit request and validate it without a design approval loop.
3. For unresolved choices, explain the tradeoff and ask one focused question.
   Do not ask the user to repeat information already provided.
4. For substantial new behavior, present the viable approaches and recommend
   one based on the existing project. Get agreement before implementing.
5. Summarize the agreed scope briefly. Write a design file only when requested
   or when the work needs a persistent specification; do not create documents
   for routine extractions or require repeated approval of unchanged decisions.
6. Once the user approves or asks to proceed, implement and test the agreed
   approach. Reopen discussion only if a new issue changes the scope or behavior.

Keep this workflow local to the project. Do not modify global skills to resolve
project-specific friction, and do not require unavailable planning skills.
