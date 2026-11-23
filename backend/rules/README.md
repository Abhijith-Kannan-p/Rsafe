# Rules

One YAML file per rule, named after its id (`STU-001.yaml`). Rules are loaded and
validated at startup by `app/services/rules.py`; a malformed rule stops the server
instead of being skipped.

```yaml
id: STU-001                 # (STU|TCH|FAC|SYS)-NNN, must match the file name
version: "1.0.0"            # semver; stamped on every issue the rule raises
title: Student name missing or malformed
severity: high              # high | medium | low
entity: student             # student | teacher | facility
scope: record               # record (default) | dataset (sees all records, for duplicates)
check: name_wellformed      # a function registered in app/services/checks.py
addresses: Name or spelling mismatch   # government-reported failure reason
params: {}                  # optional settings passed to the check
message: >
  Plain-language reason shown to the school.
fix: >
  Suggested action.
```

To change a rule's behaviour, change its `params` or its check and bump `version`.

## Translations

`i18n.json` holds each rule's title, reason and fix in English, Hindi and Malayalam. The English copy
must match the YAML exactly (`tests/test_extras.py` checks this), so when you change a rule's
`message`, `fix` or `title`, update `i18n.json` too. Hindi and Malayalam are machine translations
marked `needs_review`; the app labels them as such wherever they are shown.
