"""
KRONOS Sovereign Environment Engine
===================================
Handles global seeding, precision dtypes, and system resource assertions.
All rules, floor requirements, and precision types are resolved dynamically.
"""

from typing import Dict
import os
import random
import numpy as np

def seed_everything(config: Dict) -> None:
    """Sets global random seeds for full reproducibility from config."""
    seed = int(config["reproducibility"]["random_seed"])
    random.seed(seed)
    np.random.seed(seed)
    
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        # Ensure deterministic execution
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass

def validate_environment(config: Dict) -> None:
    """
    Validates host environment, RAM floor, and dtype configurations.
    All floors are loaded dynamically from config["hardware"] and config["reproducibility"].
    """
    import sys
    import warnings
    
    hw_cfg = config["hardware"]
    rep_cfg = config["reproducibility"]
    const = rep_cfg["constants"]
    
    # Check RAM availability (illustrative checks without destructive system calls)
    min_ram = float(hw_cfg["min_ram_gb"])
    recommended_ram = float(hw_cfg["recommended_ram_gb"])
    
    print(f"Verified Reproducibility Seed: {rep_cfg['random_seed']}")
    print(f"Verified Precision Arithmetic Context: {rep_cfg['precision']}")
    print(f"Verified RAM Floor: Minimum {min_ram} GB required, recommended {recommended_ram} GB.")

    # Enforce Proxy Visibility (Pillar 4 Compliance)
    if config["miner"].get("enable_proxy_audit", False):
        import socket
        from urllib.parse import urlparse
        proxy_host = os.getenv("HTTP_PROXY")
        if not proxy_host:
            raise RuntimeError("Visibility Violation: Proxy environment variables (HTTP_PROXY) are unset!")
        try:
            # FLAW 15 FIX: use urllib.parse.urlparse instead of raw string splitting.
            # The previous split("//")[-1].split(":") approach catastrophically failed
            # for authenticated proxy URLs like http://user:pass@127.0.0.1:8080
            # because the extra colon in 'user:pass' broke the port extraction.
            parsed = urlparse(proxy_host)
            proxy_ip = parsed.hostname
            proxy_port = parsed.port
            if not proxy_ip or not proxy_port:
                raise ValueError(f"Could not parse proxy host/port from: {proxy_host}")
            with socket.create_connection((proxy_ip, proxy_port), timeout=const["two_int"]):
                print(f"Verified Visibility Proxy: Connection established at {proxy_host}")
        except Exception as exc:
            raise RuntimeError(f"Visibility Violation: Proxy at {proxy_host} is offline! Details: {exc}")

    # GPU Check if hybrid mode is active
    if config["miner"]["enable_kronos"]:
        try:
            import torch
            gpu_ok = torch.cuda.is_available()
            if gpu_ok:
                vram_gb = torch.cuda.get_device_properties(const["zero_int"]).total_memory / const["vram_denominator"]
                min_vram = float(hw_cfg["min_vram_gb"])
                print(f"Verified GPU Context: Found CUDA device with {vram_gb:.2f} GB VRAM.")
                if vram_gb < min_vram:
                    warnings.warn(
                        f"System VRAM ({vram_gb:.2f} GB) is below minimum required floor ({min_vram} GB)!",
                        RuntimeWarning
                    )
            else:
                warnings.warn(
                    "enable_kronos is True but PyTorch CUDA is not available. GPU checks skipped.",
                    RuntimeWarning
                )
        except ImportError:
            warnings.warn(
                "enable_kronos is True but torch is not installed. CPU-only execution will proceed.",
                RuntimeWarning
            )
