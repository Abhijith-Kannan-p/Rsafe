# Rules

One YAML file per rule, loaded at startup (the loader arrives in Phase 2).

```yaml
id: STU-001
version: "1.0.0"
title: Student name missing or malformed
severity: high          # high | medium | low
entity: student         # student | teacher | facility
check: name_wellformed  # a named Python function in app/services/checks.py
message: >
  Plain-language reason shown to the school.
fix: >
  Suggested action.
```
