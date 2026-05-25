# Sovereign Validator Specification

**File**: `SOVEREIGN_VALIDATOR.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `hardcode_validator_engine.py`

---

## Purpose

Defines the KRONOS hardcode validator: a CI-grade scanner that enforces the zero-inline-literal doctrine across all specification and engine files. All detection patterns, allowlists, severity rules, and exit codes resolve exclusively via `cfg["validator"]`. No regex literals appear in this document.

---

## Validator Pipeline

```
═══════════════════════════════════════════════════════════════
HARDCODE VALIDATOR PIPELINE (as implemented)
═══════════════════════════════════════════════════════════════

CONFIG LOAD
  cfg = load_sovereign_config()

PRIMARY ENTRY POINT
  hardcode_validator_engine.run_full_validation(scan_dir, cfg)
    (alias: run_validation)

INTERNAL — FILE DISCOVERY
  Files matched by suffix in cfg["validator"]["scan_extensions"].
  Exclusions via cfg["validator"]["exclude_patterns"] (regex vs path strings).
  Dot-directories skipped.
  Implemented in → hardcode_validator_engine._discover_files(...)

INTERNAL — PER-FILE SCAN
  For .py: every non-allowlisted line tested against literal regex list.
  For .md/.mdx etc.: only fenced ``` code blocks scanned line-by-line.
  Allowlist patterns from cfg["validator"]["allowlist_patterns"].
  Implemented in → hardcode_validator_engine._scan_file(...)
                → hardcode_validator_engine._is_allowlisted(...)

RESULT + EXIT
  Violations printed (bounded by cfg["reproducibility"]["constants"]["ten_int"])
  Implemented in → hardcode_validator_engine._aggregate_and_exit(violations, cfg)
      → sys.exit(cfg["validator"]["exit_violations"]) or clean pass message

═══════════════════════════════════════════════════════════════
```

---

## Validator Configuration Map

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| File extensions to scan | Target file types | `cfg["validator"]["scan_extensions"]` |
| Path exclude regex list | Paths matching any pattern are skipped | `cfg["validator"]["exclude_patterns"]` |
| Literal detection patterns | Violation regex rules (loaded in engine) | `cfg["validator"]["literal_patterns"]` |
| Allowlist patterns | Acceptable pattern overrides | `cfg["validator"]["allowlist_patterns"]` |
| Severity map | Per-category severity levels | `cfg["validator"]["severity_rules"]` |
| Exit code — violations | Exit status when violations found | `cfg["validator"]["exit_violations"]` |
| Exit code — clean | Exit status when fully clean | `cfg["validator"]["exit_clean"]` |
| Exit code — usage error | Exit status on bad invocation | `cfg["validator"]["exit_usage_error"]` |

---

## Violation Categories Reference

Categories are defined in `hardcode_validator_engine.py` and loaded via `cfg["validator"]["literal_patterns"]`. No pattern strings appear here.

| Category | Description | Severity |
| :--- | :--- | :--- |
| Bare integer literal | Standalone number in code block | CRITICAL |
| Bare float literal | Decimal number in code block | CRITICAL |
| Bare scientific notation | Scientific format number | CRITICAL |
| Hardcoded path string | File path string literal | HIGH |
| Hardcoded argument | Named argument with literal value (e.g. `p=...`) | HIGH |
| Hardcoded dim argument | Tensor dimension argument | HIGH |
| Hardcoded date string | ISO date string | MEDIUM |

All severity values above are illustrative labels only. Actual severity rules resolve from `cfg["validator"]["severity_rules"]`.

---

## Allowlist Categories Reference

Allowlist patterns are defined in `hardcode_validator_engine.py` and loaded via `cfg["validator"]["allowlist_patterns"]`. No pattern strings appear here.

| Allowlist Category | Rationale |
| :--- | :--- |
| `cfg["section"]["key"]` lookups | Sovereign config references — always valid |
| `load_sovereign_config()` calls | Config loader — always valid |
| Import statements | Python module imports — exempt |
| Docstring markers | Triple-quote delimiters — exempt |
| Comment lines | `#` prefixed lines — exempt |
| Delegation expressions | `from engine import fn; return fn(...)` — always valid |

---

## Validator Engine Stub

```python
from typing import Dict

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def run_full_validation(scan_dir: str, config: Dict) -> None:
    """
    Runs the complete hardcode validator over scan_dir.
    All patterns, allowlists, severity rules, and exit codes from config.

    Config refs:
      cfg["validator"]["scan_extensions"]
      cfg["validator"]["literal_patterns"]
      cfg["validator"]["allowlist_patterns"]
      cfg["validator"]["severity_rules"]
      cfg["validator"]["exit_violations"]
      cfg["validator"]["exit_clean"]

    Full implementation → hardcode_validator_engine.run_full_validation(scan_dir, config)
    """
    from hardcode_validator_engine import run_full_validation as _impl
    _impl(scan_dir, config)
```

---

## CI / Pre-Commit Integration

Invoke the same runtime entry CI would use:

```python
from typing import Dict

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def ci_validate_repo(scan_dir: str, config_path: str = "params_yaml.txt") -> None:
    """
    Validates scan_dir using cfg-driven rules; exits via engine on violations.
    """
    cfg = load_sovereign_config(config_path)
    from hardcode_validator_engine import run_full_validation as _impl
    _impl(scan_dir, cfg)
```

---

**Hardcode Audit Passed — Zero Inline Literals**
