# Altcoin References and External Context

**File**: `ALTCOIN_REFERENCES_AND_EXTERNAL_CONTEXT.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`

---

## Purpose

Provides complete, queryable context for any engineer or AI agent working on the Altcoin KRONOS Hybrid project. Documents external inspirations, research foundations, tooling references, and philosophical constraints tailored for large-scale, cross-sectional altcoin processing on high-performance cloud infrastructure. All quantitative model specifications referenced here link to config keys — no inline values.

---

## Core Model References

### Kronos Foundation Model (Primary Neural Component)

| Property | Reference | Config Lookup |
| :--- | :--- | :--- |
| Repository | `shiyu-coder/Kronos` (GitHub) | — |
| Mini variant used | `cfg["kronos_mini"]["model_name"]` | `cfg["kronos_mini"]["model_name"]` |
| Tokenizer used | `cfg["kronos_mini"]["tokenizer_name"]` | `cfg["kronos_mini"]["tokenizer_name"]` |
| Bottleneck embedding width | Resolved at runtime | `cfg["kronos_mini"]["embedding_dim"]` |
| Context window length | Resolved at runtime | `cfg["kronos_mini"]["context_length"]` |
| Pooling strategy | Resolved at runtime | `cfg["kronos_mini"]["pooling"]["method"]` |
| Weight integrity | SHA-256 pinned | `cfg["kronos_mini"]["model_sha256"]` |

**Deep Insight**: Kronos is a decoder-only Transformer trained on a large corpus of financial candlestick records across multiple exchanges. It treats raw price sequences as a language and excels at structural sequence understanding. In Altcoin KRONOS Hybrid, the frozen Kronos-mini variant produces bottleneck embeddings that serve as an orthogonal conviction signal complementing the pure structural sovereign core. The embedding width is defined in `cfg["kronos_mini"]["embedding_dim"]` and never hardcoded. This approach is scaled across `cfg["universe"]["size"]` perpetual altcoin pairs.

---

## Methodology References

### Altcoin Cross-Sectional Analysis

| Property | Reference | Config Lookup |
| :--- | :--- | :--- |
| Scope | Perpetual Altcoins | `cfg["universe"]["size"]` |
| Timeframe | Base processing interval | `cfg["feature_builder"]["interval"]` |
| History | Full historical data | `cfg["data"]["historical_range"]` |
| Compute Infrastructure | Cloud-based parallel processing | `cfg["infrastructure"]["compute_provider"]` |

**Deep Insight**: The Altcoin KRONOS Hybrid shifts from single-asset focus to a massive cross-sectional processing pipeline spanning `cfg["universe"]["size"]` assets. The temporal resolution operates at `cfg["feature_builder"]["interval"]` frequency, ingesting `cfg["data"]["historical_range"]` history to capture long-term structural market regimes across the altcoin universe. Heavy computation is delegated to `cfg["infrastructure"]["compute_provider"]`.

### Harvard Algorithmic Trading with AI

| Property | Reference |
| :--- | :--- |
| Repository | `moondevonyt/Harvard-Algorithmic-Trading-with-AI` (GitHub) |
| Framework | RBI — Research → Backtest → Implement |

**Deep Insight**: Introduces the RBI Framework as the high-level development philosophy for systematic, non-emotional trading system design. It maps directly to the KRONOS pipeline: Feature Builder → Miner → Signature Database. Walk-forward folds (`cfg["backtest"]["fold_window_days"]`) and ablation runs (`cfg["miner"]["enable_ablation"]`) embody the Backtest and Implement phases. In the altcoin context, folds are synchronized across the entire `cfg["universe"]["size"]` asset matrix.

---

## AI Agent and Development Tooling References

### SkillKit

| Property | Reference |
| :--- | :--- |
| Repository | `rohitg00/skillkit` (GitHub) |

**Deep Insight**: A universal skill and package manager for agentic workflows enabling consistent agent capabilities across multi-agent pipelines. Relevant for orchestrating the Altcoin KRONOS specification-driven multi-engine architecture across massive concurrent tasks.

### GBrain

| Property | Reference |
| :--- | :--- |
| Repository | `garrytan/gbrain` (GitHub) |

**Deep Insight**: A long-term memory system for AI agents with persistent knowledge layers. Ideal for building a structural memory layer so agent sessions remember KRONOS sovereign rules, past design trade-offs, and the zero-inline-literal doctrine even across massive parallel asset evaluations.

### AI Factory

| Property | Reference |
| :--- | :--- |
| Repository | `lee-to/ai-factory` (GitHub) |

**Deep Insight**: A zero-configuration, AI-powered development environment for orchestrating workflows and context setup. Suitable for multi-agent, spec-driven codebases such as Altcoin KRONOS.

---

## Important Discussions and Context

| Discussion | Author | Core Insight |
| :--- | :--- | :--- |
| Kronos viral introduction | `@sharbel` | Introduced Kronos as an open-source model treating financial markets as a language — the genesis of the KRONOS Hybrid architecture |
| Motus Tracing | `@JiaZhihao` | Open-source observability for AI agents — critical for tracing decisions in mining and coding pipelines |
| Momentum repositories | `@sharbel` | Growing GitHub repositories in agent toolbelt space |
| Multi-hop reasoning | `@tom_doerr` | Automation tools scaling complex multi-hop agent reasoning loops |
| Trinity-Large-Thinking | `@arcee_ai` | High-capability models for software planning and architecture analysis |
| AI-native engineering teams | `@Voxyz_ai` | Building AI-native engineering workflows |
| Developer loop automation | `@jahooma` | Complex agent workflow state automation |
| Schema-aware AI plugins | `@supabase` | Schema-aware plugins relevant if KRONOS signature database scales to relational DBs |

---

## Project Philosophy and Constraints

| Principle | Statement | Config Enforcement |
| :--- | :--- | :--- |
| Mathematical Sovereignty | Long-term north star — pure deterministic features, no neural weights, no external dependencies | `cfg["miner"]["enable_kronos"]`, `cfg["miner"]["enable_ablation"]` |
| Current Mode | Deliberate hybrid: structural sovereign core + Kronos-mini for short-term edge boost | `cfg["miner"]["enable_kronos"]: True` |
| Cross-Sectional Scale | Processing scales universally across all available altcoin perpetuals via cloud computing | `cfg["universe"]["size"]`, `cfg["infrastructure"]["compute_provider"]` |
| Causal Purity | All feature computations strictly bounded to `df.iloc[:t + one_i]` | `cfg["reproducibility"]["constants"]["one_int"]` |
| Zero Inline Literals | Every numerical value, path, and string key resolves via `cfg["section"]["key"]` | `cfg["validator"]` |
| Bit-Perfect Reproducibility | Identical results given identical config, seed, and data | `cfg["reproducibility"]["random_seed"]`, `cfg["reproducibility"]["enforce_pinning"]` |
| Signature Durability | Every archive entry is audited with data hash, config hash, and git commit | `cfg["database"]["audit"]` |

---

**Hardcode Audit Passed — Zero Inline Literals**
