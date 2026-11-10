# Technology sources

The project bibliography is [references.bib](../references.bib). These ten entries were supplied by the project author. Their metadata, access dates, and specification descriptions are retained as supplied; this addition does not independently verify them or convert the synthetic demo into measured hardware profiles.

| Technology or context | BibTeX keys | Parameter provenance and modeling boundary |
|---|---|---|
| NVIDIA T4 / GDDR6 baseline | `nvidia_t4` | Vendor device specifications. Keep vendor peak compute/bandwidth separate from locally measured sustained roofs. |
| GDDR6 configurations | `micron_gddr6` | Record data rate, bus width and system configuration when deriving aggregate bandwidth. A 384-bit system is a configuration, not a universal GDDR6 property. |
| HBM2E / AMD MI250 | `amd_mi250` | Whole-accelerator specification scope. Retaining another device's compute roof makes this a memory-only counterfactual. |
| HBM3E | `micron_hbm3e`, `micron_hbm` | Record capacity variant, stack count and per-stack versus system bandwidth. |
| HBF architecture | `ocp_hbf_v070` | Architecture/interface reference. Cite exact document revision, section and derivation when adding a numeric profile. Interface bandwidth does not establish sustained flash throughput. |
| HBF simulation | `hbfsim2026` | Simulator and research context. Simulation assumptions and results need their own configuration provenance. |
| Samsung HBM-PIM | `samsung_hbmpim` | PIM capability context. Verify operation set and precision before comparing compute roofs; document any separately constructed bandwidth configuration. |
| DDR5 | `micron_ddr5` | Component data rates and organization. System bandwidth also depends on configured channels and bus width. |
| LPDDR5X | `micron_lpddr5x` | Per-pin rate and capacity context. Record actual rate and aggregate bus width for each modeled system. |

## Attach a source to an experiment

The CLI's existing `evidence` field is retained in both the Markdown report and projection CSV. Include a bibliography key, document location, parameter scope, and the conversion from published values to the modeled sustained value. For example:

```json
{
  "evidence": "micron_hbm3e; product brief Rev C; per-stack scope; bandwidth_gbs is an explicit sustained-bandwidth assumption, not a measured value"
}
```

Supply the complete scenario fields alongside this provenance. Merely attaching a citation does not verify a scenario's parameters.

## Keep assumptions explicit

- HBF useful-bandwidth fractions, page utilization, request latency, and sustainable concurrency must each have a measurement, a precise source, or an assumption label.
- Capacity units must match the CLI's decimal GB: convert GiB using `GB = GiB * 2**30 / 1e9`. Do not enter a GiB value unchanged as GB.
- Distinguish memory-only comparisons from complete accelerator comparisons. Reusing baseline compute is an explicit counterfactual.
- A PIM compute figure needs its operation/precision context. A constructed pairing of PIM compute and representative HBM bandwidth is not automatically a validated product configuration.
- For reproducible references, supplement landing pages with the exact document revision or stable artifact location when available.
