# Validator and Hardware Specification

**File**: `VALIDATOR_AND_HARDWARE_SPEC.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `hardcode_validator_engine.py`, `environment_engine.py`

---

## Purpose

Defines the hardware requirements for running KRONOS and the environment validation contract. All memory bounds, VRAM requirements, precision settings, and runtime environment keys resolve exclusively via `cfg["section"]["key"]`. No inline specifications appear.

---

## True Reverse Engineering Pipeline — Environment Validation Flow

```
═══════════════════════════════════════════════════════════════
ENVIRONMENT VALIDATION FLOW
═══════════════════════════════════════════════════════════════

CONFIG LOAD
  cfg = load_sovereign_config()

PRECISION ASSERTION
  precision_str = cfg["reproducibility"]["precision"]
  Full implementation → environment_engine.assert_torch_dtype(precision_str)

RANDOM SEED ASSERTION
  seed = cfg["reproducibility"]["random_seed"]
  Full implementation → environment_engine.seed_everything(seed)

GPU AVAILABILITY CHECK (if enable_kronos)
  if cfg["miner"]["enable_kronos"]:
    Full implementation → environment_engine.assert_gpu_available(cfg)

MODEL WEIGHT INTEGRITY CHECK
  Full implementation → neural_integration_engine.load_verified_model(cfg)
  Full implementation → neural_integration_engine.load_verified_tokenizer(cfg)

HARDCODE SCAN (all spec files)
  Full implementation → hardcode_validator_engine.run_validation(cfg)

═══════════════════════════════════════════════════════════════
```

---

## Hardware Requirements Map

All hardware bounds are defined in `params_yaml.txt` under `hardware.*`. No specifications appear as inline values here.

| Requirement | Description | Config Reference Key |
| :--- | :--- | :--- |
| Minimum system RAM | Host memory floor for mining | `cfg["hardware"]["min_ram_gb"]` |
| Recommended system RAM | Optimal host memory for full pipeline | `cfg["hardware"]["recommended_ram_gb"]` |
| GPU minimum VRAM (hybrid mode) | VRAM floor for Kronos-mini inference | `cfg["hardware"]["min_vram_gb"]` |
| GPU recommended VRAM | Optimal VRAM for full batch inference | `cfg["hardware"]["recommended_vram_gb"]` |
| Storage minimum | Minimum disk for Parquet archive | `cfg["hardware"]["min_storage_gb"]` |
| Inference precision | PyTorch dtype string | `cfg["reproducibility"]["precision"]` |
| AMP enabled flag | Automatic Mixed Precision toggle | `cfg["feature_builder"]["amp_enabled"]` |
| GPU requirement toggle | Enable/disable GPU dependency | `cfg["miner"]["enable_kronos"]` |

---

## Runtime Environment Configuration Map

| Environment Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Random seed | Global reproducibility seed | `cfg["reproducibility"]["random_seed"]` |
| Precision string | Arithmetic context for all computation | `cfg["reproducibility"]["precision"]` |
| Weight pinning flag | Enforce SHA-256 checksum verification | `cfg["reproducibility"]["enforce_pinning"]` |
| Model weight checksum | Kronos-mini integrity hash | `cfg["kronos_mini"]["model_sha256"]` |
| Tokenizer checksum | Kronos tokenizer integrity hash | `cfg["kronos_mini"]["tokenizer_sha256"]` |

---

## Sovereign Mode (CPU-Only) Profile

When `cfg["miner"]["enable_kronos"]` is disabled, the pipeline runs entirely on CPU with no GPU dependency:

| Property | Sovereign Mode Value | Config Reference Key |
| :--- | :--- | :--- |
| GPU required | Disabled (resolved at runtime) | `cfg["miner"]["enable_kronos"]` |
| Neural slots populated | Disabled | `cfg["miner"]["enable_ablation"]` |
| Precision | CPU-compatible precision | `cfg["reproducibility"]["precision"]` |
| Active slots | Structural sovereign + metadata only | `cfg["feature_builder"]["structural"]`, `cfg["feature_builder"]["metadata"]` |

---

## Environment Engine Stubs

```python
from typing import Dict

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def validate_environment(config: Dict) -> None:
    """
    Runs full environment validation before pipeline start.
    All assertions resolved from config.

    Config refs:
      cfg["reproducibility"]["precision"]
      cfg["reproducibility"]["random_seed"]
      cfg["reproducibility"]["enforce_pinning"]
      cfg["miner"]["enable_kronos"]
      cfg["hardware"]["min_ram_gb"]
      cfg["hardware"]["min_vram_gb"]
      cfg["kronos_mini"]["model_sha256"]
      cfg["kronos_mini"]["tokenizer_sha256"]

    Full implementation → environment_engine.validate_environment(config)
    """
    from environment_engine import validate_environment as _impl
    _impl(config)

def seed_everything(config: Dict) -> None:
    """
    Sets global random seeds for full reproducibility.
    Seed value from config.

    Config refs:
      cfg["reproducibility"]["random_seed"]

    Full implementation → environment_engine.seed_everything(config)
    """
    from environment_engine import seed_everything as _impl
    _impl(config)
```

---

**Hardcode Audit Passed — Zero Inline Literals**
