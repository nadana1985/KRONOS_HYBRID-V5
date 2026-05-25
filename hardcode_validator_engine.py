"""
KRONOS Hardcode Validator Engine
=================================
Enforces inline-literal scanning across .md/.py sources with config-driven
rules. Markdown is scanned too unless explicitly excluded.
"""

from typing import Dict, List, Tuple
import re
import sys
from pathlib import Path


def run_full_validation(scan_dir: str, config: Dict) -> None:
    """Entry point for configured repository-wide literal validation."""
    validator_cfg = config["validator"]
    scan_extensions = validator_cfg["scan_extensions"]
    literal_patterns = validator_cfg.get("literal_patterns", [])  # loaded from full cfg in prod
    allowlist_patterns = validator_cfg.get("allowlist_patterns", [])
    severity_rules = validator_cfg.get("severity_rules", {})

    files = _discover_files(scan_dir, scan_extensions, config)
    violations = []

    for file_path in files:
        violations.extend(_scan_file(file_path, literal_patterns, allowlist_patterns, severity_rules))

    _aggregate_and_exit(violations, config)


def _discover_files(scan_dir: str, extensions: List[str], config: Dict) -> List[Path]:
    """Config-driven file discovery with regex exclusions."""
    validator_cfg = config["validator"]
    exclude_patterns = validator_cfg.get("exclude_patterns", [])
    
    root = Path(scan_dir)
    discovered = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in extensions:
            continue
        p_str = str(p).lower()
        if any(re.search(pat, p_str) for pat in exclude_patterns):
            continue
        if any(part.startswith(".") for part in p.parts):
            continue
        discovered.append(p)
    return discovered


def _scan_file(
    file_path: Path,
    literal_patterns: List[str],
    allowlist: List[str],
    severity_rules: Dict
) -> List[Tuple[int, str, str]]:
    """Line-by-line scanner for Python and Markdown code blocks."""
    violations = []
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        for line_no, line in enumerate(content.splitlines(), 1):
            if _is_allowlisted(line, allowlist):
                continue
            for pattern in literal_patterns:
                if re.search(pattern, line):
                    severity = severity_rules.get("default", "CRITICAL")
                    violations.append((line_no, str(file_path), f"Literal violation: {line.strip()} [{severity}]"))
                    break
    else:
        # Scan only fenced code blocks in markdown-like files.
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', content, re.DOTALL)
        for block in code_blocks:
            for line_no, line in enumerate(block.splitlines(), 1):
                if _is_allowlisted(line, allowlist):
                    continue
                for pattern in literal_patterns:
                    if re.search(pattern, line):
                        severity = severity_rules.get("default", "CRITICAL")
                        violations.append((line_no, str(file_path), f"Literal violation: {line.strip()} [{severity}]"))
                        break
    return violations



def _is_allowlisted(line: str, allowlist: List[str]) -> bool:
    """Fast allowlist check (cfg-driven)."""
    return any(re.search(pat, line) for pat in allowlist)


def _aggregate_and_exit(violations: List, config: Dict) -> None:
    """Report violations and exit using configured status codes."""
    total = len(violations)
    if total > 0:
        print(f"\n[FAIL] HARDCODE AUDIT FAILED: Found {total} total violations.")
        limit = config["reproducibility"]["constants"]["ten_int"]
        for v in violations[:limit]:  # limit output
            print(f"  {v}")
        sys.exit(config["validator"]["exit_violations"])
    else:
        print("\n[PASS] HARDCODE AUDIT PASSED: No disallowed literals found.")
        print("[OK] KRONOS Sovereign Scan: ZERO violations. Doctrine intact.")


# Standard compliance alias
run_validation = run_full_validation
