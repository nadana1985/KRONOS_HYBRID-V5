# Altcoin Kronos Hybrid — Lightning AI L4 Launch Guide

## Step-by-step to start mining

---

### Step 1 — Open Lightning AI Studio with L4

1. Go to **https://lightning.ai**
2. Create a new **Studio**
3. In the compute selector, choose **L4 GPU** (24 GB VRAM)
4. Wait for the Studio to initialise

---

### Step 2 — Upload the repo

**Option A — Git (recommended if you have a private repo)**
```bash
git clone https://github.com/YOUR_ORG/altcoin-kronos-hybrid.git
cd altcoin-kronos-hybrid
```

**Option B — Zip upload via Lightning AI file browser**
1. Zip the entire `Altcoin Kronos Hybrid` folder on your local machine:
   ```powershell
   # On Windows (PowerShell):
   Compress-Archive -Path "G:\KRONOS HYBRID\Altcoin Kronos Hybrid\*" -DestinationPath "G:\altcoin_kronos_hybrid.zip"
   ```
2. Drag and drop `altcoin_kronos_hybrid.zip` into the Lightning AI file browser
3. Unzip in the Studio terminal:
   ```bash
   unzip altcoin_kronos_hybrid.zip -d altcoin_kronos_hybrid
   cd altcoin_kronos_hybrid
   ```

---

### Step 3 — Run the setup script (one time only)

```bash
cd /teamspace/studios/this_studio/altcoin_kronos_hybrid   # adjust path to your upload location
bash lightning_setup.sh
```

This will:
- Install all Python packages (`torch` with CUDA 12.1, `hdbscan`, `pyarrow`, etc.)
- Verify the L4 GPU is visible
- Validate `params_yaml.txt` sovereign config
- Run the hardcode sovereignty validator

Expected output at the end:
```
[OK] Sovereignty validator passed. Zero inline literals detected.
SETUP COMPLETE. ALTCOIN KRONOS HYBRID is ready to mine.
```

---

### Step 4 — Start the mining run

```bash
bash start_mining.sh
```

This launches `run_sharded_pipeline.py` inside a **tmux** session called `kronos_mining`.  
The run will **survive disconnects** — you can close your browser and it keeps running.

---

### Step 5 — Monitor progress

**Attach to live output:**
```bash
tmux attach -t kronos_mining
# Detach without stopping: Ctrl+B, then D
```

**Dashboard snapshot (run any time):**
```bash
bash monitor_mining.sh
```

Example output:
```
================================================================
 ALTCOIN KRONOS HYBRID — Mining Monitor 
================================================================
 Session  : [RUNNING] kronos_mining
 Shards   : cfg["pipeline"]["completed_shards"] completed
 Range    : cfg["data"]["start_date"] → cfg["data"]["end_date"]
 Sigs DB  : partition tree, multiple files
 Universe : cfg["universe"]["size"] perpetual altcoins
 Interval : cfg["feature_builder"]["interval"]

--- GPU Status ---
 GPU       : NVIDIA L4 | Util: 78% | VRAM: 8241/23028 MiB | Temp: 64°C
```

---

### Step 6 — After mining completes

The pipeline will automatically:
1. Compact the partition tree → `data/signatures_compact.parquet`
2. Run the **Global Ontology Compiler** → writes stable `slot_28` phylum labels
3. Refresh the DuckDB view
4. Generate `SIGNATURES_WIKI.md`

You will see:
```
[POST] Post-run optimization completed successfully!
```

Then download the results:
```bash
# Zip just the database output
zip -r kronos_results.zip data/signatures_compact.parquet data/shard_checkpoint.json SIGNATURES_WIKI.md logs/
```

---

### Useful commands

| Command | Purpose |
|---|---|
| `bash start_mining.sh` | Start / resume mining |
| `bash monitor_mining.sh` | Check progress snapshot |
| `tmux attach -t kronos_mining` | Live log stream |
| `tmux kill-session -t kronos_mining` | Stop mining |
| `tail -f logs/mining_*.log` | Follow raw log output |
| `nvidia-smi` | GPU real-time status |

---

### If the run is interrupted mid-way

Just re-run:
```bash
bash start_mining.sh
```

The checkpoint file `data/shard_checkpoint.json` tracks completed monthly shards.  
The pipeline resumes from the last incomplete shard automatically. No data is lost.

---

### Expected runtime on L4

| Date range | Approx shards | Estimated time |
|---|---|---|
| cfg["data"]["start_date"] → cfg["data"]["end_date"] | ~cfg["pipeline"]["total_shards"] shards | Dependent on cfg["universe"]["size"] |

> The L4's 24 GB VRAM comfortably holds the models and cross-sectional data for cfg["universe"]["size"] altcoins at a cfg["feature_builder"]["interval"] interval. The bottleneck is the structural
> slot computation (HMM + KDE + Hurst), not the neural forward pass.
