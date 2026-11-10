# MemSpaceExplorer

Explore which memory scenarios are worth investigating for each measured workload phase. A Python 3.9+ CLI with no third-party dependencies. No GPU is required: bring results from a benchmark you already ran.

## Run

```bash
python memspace.py
```

The wizard asks for your baseline's sustained compute and memory bandwidth, phase measurements, and the candidate scenarios you want to explore. To try the included synthetic example:

```bash
python memspace.py --input demo.json --out results/demo
python -m unittest discover -s tests -v
```

Outputs: `input.json` for reproducibility, `report.md` for explanations, and `projections.csv` containing the individual timing terms. Running again in the same output directory replaces these files.

## Inputs

For each phase supply FLOPs, reads plus writes in bytes, and measured runtime for the **same invocation scope**. Count FMA as two FLOPs. Enter aggregate phase counters, not per-kernel averages paired with a total phase runtime. Use consistent precision and compatible operations for the compute calibration. Normalize profiler replay counters to the benchmark's invocation count.

| Field | Meaning |
|---|---|
| `flops` | Arithmetic operations per phase invocation; zero means known non-arithmetic work |
| `bytes` | Traffic per invocation, not allocation size |
| `time_ms` | Measured phase duration in milliseconds |
| `traffic_basis` | `measured_dram` or `analytic`; these are different modeling assumptions |
| `working_set_gb` | Resident data footprint, decimal GB; optional |
| `access` | `sequential`, `random`, or `unknown` |
| `write_fraction` | Fraction of traffic bytes written, 0 to 1; optional |
| `pim_compatible` | Whether the candidate PIM operations and precision were verified; true, false, or null |

Missing FLOPs are not replaced with zero. If counters are unavailable, collect them or provide a documented analytic estimate. This MVP requires FLOPs, bytes, and timing rather than silently inventing data. Optional measurements remain unknown.

Use the JSON example as the configuration schema. Each technology must provide `name`, `bandwidth_gbs`, and `evidence`. Bandwidth means sustained physical bandwidth **before** useful-page utilization. Do not apply an efficiency penalty twice. Optional fields: `kind` (`memory`, `hbf`, `pim`), `capacity_gb`, `compute_gflops`, `page_utilization` (default 1), `latency_us` (default 0), `page_bytes`, `concurrency`, `supports_writes`, and `extra_ms` (default 0).

A latency model requires page size and sustainable concurrency. HBF requires explicit latency. PIM requires an explicit compatible compute roof. Compare the same number of stacks/channels, or clearly name each scenario's system scope. A per-stack value and a full-system value describe different configurations.

## Model

All bandwidths and capacities use decimal GB. Internal timing terms are milliseconds.

- Arithmetic intensity: `FLOPs / bytes`
- Baseline ridge: `compute_GFLOPs / bandwidth_GBs`
- Compute bound: `FLOPs / (compute_GFLOPs * 1e6)`
- Physical traffic: `bytes / page_utilization`
- Bandwidth bound: `physical_bytes / (bandwidth_GBs * 1e6)`
- Request latency bound: `ceil(ceil(physical_bytes / page_bytes) / concurrency) * latency_us / 1000`
- Scenario bound: `max(compute, bandwidth, latency) + extra_ms`
- Roof ratio: `modeled_baseline_bound / scenario_bound`

The maximum assumes ideal overlap. The request model assumes independent, evenly filled waves. It does not establish that the workload can sustain the supplied concurrency. `extra_ms` can represent a separately estimated transfer/offload cost per phase. Dependent transfers may require a more detailed execution model.

## Interpret results

The report distinguishes **the roof model's limiting resource** from evidence about an observed bottleneck. Low achieved performance relative to a roof triggers investigation of overhead, occupancy and dependencies. A measured runtime below the bound triggers a counter/calibration consistency check.

Recommendations are conditional candidates, not measured speedup claims or purchase advice. Known capacity failures, unsupported writes, and incompatible PIM operations exclude a scenario. Unknown capacity, write behavior, and PIM compatibility are shown explicitly. Write-intensive HBF phases require a write-performance/endurance model before acting on a read-only latency projection.

The PIM compatibility flag is phase-wide in this MVP; if comparing different PIM instruction sets, use separate configurations with separately verified flags. Baseline DRAM traffic may change with another cache or PIM mapping. Analytic traffic does not automatically equal physical memory traffic. No PIM traffic reduction is inferred. No end-to-end total is inferred because phases may overlap or have different frequencies. Capacity is a per-phase check; simultaneous residency and tier movement are not modeled.

## Scope and next steps

The bundled HBM-like, HBF-like and PIM-like numbers are synthetic assumptions, **not a sourced hardware database**. The uploaded notebook's vendor rows were deliberately not copied into default recommendations. A credible product catalog should record exact source documents, dates, precision, system scope, sustained-versus-interface status, and uncertainty ranges.

Useful next additions: normalized profiler CSV import with explicit column mappings, per-phase/per-device PIM eligibility, HBF latency/concurrency/utilization sweeps, sourced and versioned technology profiles, and plots. The present CLI supports manual sweeps through reproducible JSON configurations.

Before publishing, choose a license and replace synthetic profiles with independently checked examples. This archive is a local starter project; it does not create a GitHub repository.

## Technology references

[references.bib](references.bib) includes the ten supplied NVIDIA, Micron, AMD, OCP, Samsung, and HBFSim references. See [the technology-to-source mapping](docs/technology_sources.md) for scope and parameter-provenance notes, including DDR5 and LPDDR5X. Reference keys can be placed in each scenario's `evidence` field and will appear in generated reports and CSV exports. These bibliographic additions do not replace the synthetic demonstration values with verified device profiles.
