import sys
import os
import time
import yaml

with open("params_yaml.txt") as f:
    cfg = yaml.safe_load(f)

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
kronos_module_path = os.path.join(parent_dir, "kronos_module")
if kronos_module_path not in sys.path:
    sys.path.insert(0, kronos_module_path)

print("Path inserted:", sys.path[0])

print("Importing Kronos...")
from model import Kronos, KronosTokenizer

print("Loading model...")
t0 = time.time()
model = Kronos.from_pretrained(cfg["kronos_mini"]["model_name"], local_files_only=True)
print(f"Model loaded in {time.time() - t0:.2f} seconds.")

print("Loading tokenizer...")
t0 = time.time()
tokenizer = KronosTokenizer.from_pretrained(cfg["kronos_mini"]["tokenizer_name"], local_files_only=True)
print(f"Tokenizer loaded in {time.time() - t0:.2f} seconds.")
