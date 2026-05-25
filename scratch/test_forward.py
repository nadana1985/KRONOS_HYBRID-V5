import sys
import os
import time
import yaml
import torch
import numpy as np

with open("params_yaml.txt") as f:
    cfg = yaml.safe_load(f)

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
kronos_module_path = os.path.join(parent_dir, "kronos_module")
if kronos_module_path not in sys.path:
    sys.path.insert(0, kronos_module_path)

from model import Kronos, KronosTokenizer

print("Loading model and tokenizer...")
model = Kronos.from_pretrained(cfg["kronos_mini"]["model_name"], local_files_only=True)
tokenizer = KronosTokenizer.from_pretrained(cfg["kronos_mini"]["tokenizer_name"], local_files_only=True)

# Prepare dummy inputs of length 530 (representing sequence length at bar 530)
seq_len = 530
print(f"Preparing dummy inputs of sequence length {seq_len}...")
x_batch = np.random.randn(1, seq_len, 6).astype(np.float32)
stamp = np.random.randint(0, 5, size=(1, seq_len, 5)).astype(np.float32)

device = next(model.parameters()).device
x_tensor = torch.tensor(x_batch.tolist(), dtype=torch.float32).to(device)
stamp_tensor = torch.tensor(stamp.tolist(), dtype=torch.float32).to(device)

print("Running tokenizer.encode...")
t0 = time.time()
with torch.no_grad():
    s1_ids, s2_ids = tokenizer.encode(x_tensor, half=True)
print(f"tokenizer.encode finished in {time.time() - t0:.4f} seconds.")
print("s1_ids shape:", s1_ids.shape)
print("s2_ids shape:", s2_ids.shape)

print("Running model.decode_s1...")
t0 = time.time()
with torch.no_grad():
    s1_logits, context = model.decode_s1(s1_ids, s2_ids, stamp=stamp_tensor)
print(f"model.decode_s1 finished in {time.time() - t0:.4f} seconds.")
print("context shape:", context.shape)

print("Converting context to list...")
t0 = time.time()
last_hidden_list = context[0, -1, :8].cpu().float().tolist()
print(f"Context to list finished in {time.time() - t0:.4f} seconds.")
print("last_hidden_list:", last_hidden_list)
