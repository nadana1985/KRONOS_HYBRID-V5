import torch
import time

print("Creating dummy tensor...")
t = torch.randn(1000000) # 1 Million elements

print("Method 1: tolist() timing...")
t0 = time.time()
lst = t.tolist()
print(f"tolist() finished in {time.time() - t0:.4f} seconds.")

print("Method 2: untyped_storage() bytes timing...")
t0 = time.time()
try:
    if hasattr(t, "untyped_storage"):
        raw_bytes = bytes(t.untyped_storage())
    else:
        raw_bytes = bytes(t.storage())
    print(f"untyped_storage() finished in {time.time() - t0:.4f} seconds (Size: {len(raw_bytes)} bytes).")
except Exception as e:
    print("Failed untyped_storage:", e)
