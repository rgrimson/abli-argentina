# abli-argentina

**Beyond the Map: Coverage, Governance and Management of Argentina's Area-Based Legal Instruments for Conservation**

Gabriela González Trilla · Germán Baldi · Carolina Luchetti · Pablo Pereira · Rafael Grimson

*Oryx* (submitted, 2026)

---

## What this repository contains

Code and derived data tables to fully reproduce the quantitative analysis
reported in the paper above. The analysis quantifies how much of
Argentina's continental territory is covered by each of eight area-based
legal instruments, individually and in combination, disaggregated by
province and ecoregion.

This GitHub repository hosts the **code and processed outputs**. The
**raw spatial inputs** (~3 GB of shapefiles, public-domain government
data not always trivially accessible) are deposited separately on Zenodo
to keep this repository lightweight:

- **Raw data archive (Zenodo)**: [doi.org/10.5281/zenodo.20451157](https://doi.org/10.5281/zenodo.20451157) **

To reproduce the analysis from scratch, download the raw archive from
Zenodo and unpack it into `data/raw/`. To reproduce **only the final
figures and tables** of the paper, no download is needed: the CSV files
in `data/processed/` are committed here and the figure/table scripts
read directly from them.

---

## Repository structure

```
abli-argentina/
├── data/
│   ├── raw/                        # Input spatial data — NOT committed; download from Zenodo
│   │   ├── protected_areas/        # Public PAs, private reserves, other conserved areas
│   │   ├── native_forests/         # OTBN — provincial native forest zoning shapefiles
│   │   ├── glaciers/               # National Glacier Inventory (NGI)
│   │   ├── ecoregions/             # Terrestrial ecoregions of Argentina
│   │   ├── provinces/              # Provincial and continental boundaries
│   │   └── natural_earth/          # Country borders for cartographic context
│   ├── interim/                    # Intermediate GeoPackages — auto-generated, not committed
│   └── processed/                  # Final CSV tables — committed
│       ├── areas_by_province.csv           # km² per province per category
│       ├── pct_by_province.csv             # % of provincial area
│       ├── areas_by_ecoregion.csv          # km² per ecoregion per category
│       ├── pct_by_ecoregion.csv            # % of ecoregion area
│       ├── areas_by_province_ecoregion.csv # km² per province × ecoregion
│       └── pct_by_province_ecoregion.csv   # % of province × ecoregion area
├── src/
│   ├── 01_compute_coverage.py      # Compute all CSV tables from raw shapefiles
│   ├── figure1_map.py              # Figure 1 — integrated mosaic map (EN + ES)
│   ├── figure2_ecoregion.py        # Figure 2 — coverage by ecoregion (EN + ES)
│   ├── figureS1_province.py        # Supplementary Figure 1 — coverage by province (EN + ES)
│   ├── tableS1_ecoregion.py        # Supplementary Table 1 — XLSX + CSV (EN + ES)
│   └── tableS2_province.py         # Supplementary Table 2 — XLSX + CSV (EN + ES)
├── output/
│   ├── figures/                    # Figure outputs (PDF + PNG)
│   └── tables/                     # Formatted tables (XLSX + CSV)
├── requirements.txt
├── LICENSE                         # MIT — applies to code
└── README.md
```

---

## Instrument categories

Coverage is reported as a **cumulative nested union**: each category includes
all territory covered by all stricter categories. The ordering reflects
decreasing legal stringency and governance robustness.

| Code | Instrument | Paper level |
|------|-----------|:-----------:|
| C10 | Strict protected areas (IUCN I–IV) | A |
| C13 | + Glaciers Law (Law 26.639 / NGI) | B |
| C16 | + Native Forests Category I (OTBN) | B |
| C20 | + Multi-use protected areas (IUCN V–VI) | C |
| C23 | + Native Forests Category II (OTBN) | C |
| C30 | + Unclassified public protected areas | D |
| C40 | + Private reserves | D |
| C50 | + International designations and other conserved areas | D |

---

## Reproducing the analysis

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

Python ≥ 3.10 recommended. Tested with geopandas 1.1, pyogrio 0.12,
shapely 2.1, matplotlib 3.10.

### 2. (Optional) Download raw data

Only needed if you want to re-run the full geospatial pipeline from
shapefiles. Skip this step to reproduce only the figures and tables.

```bash
# Download from Zenodo
wget https://zenodo.org/record/XXXXXXX/files/abli-argentina-raw.zip
unzip abli-argentina-raw.zip -d data/raw/
```

### 3. Compute coverage tables (optional, only if regenerating from raw)

```bash
python src/01_compute_coverage.py
```

The script runs in three phases:

- **Phase 1** — Per-province cumulative coverage unions
- **Phase 2** — Province × ecoregion intersection
- **Phase 3** — Final tables written to `data/processed/`

Each phase caches its output to `data/interim/` and skips on re-run
unless `--force` is passed. To run a specific phase only:

```bash
python src/01_compute_coverage.py --phase 1   # provinces
python src/01_compute_coverage.py --phase 2   # province × ecoregion
python src/01_compute_coverage.py --phase 3   # final tables only
```

### 4. Generate figures and tables

Each script is independent and reads from `data/processed/`. All five
generate bilingual outputs (English + Spanish):

```bash
python src/figure1_map.py            # Figure 1 (PDF + PNG)
python src/figure2_ecoregion.py      # Figure 2 (PDF + PNG)
python src/figureS1_province.py      # Supplementary Figure 1 (PDF + PNG)
python src/tableS1_ecoregion.py      # Supplementary Table 1 (XLSX + CSV)
python src/tableS2_province.py       # Supplementary Table 2 (XLSX + CSV)
```

Spanish versions are saved with the `_esp` suffix. Outputs land in
`output/figures/` and `output/tables/`.

---

## Methodology summary

Geospatial processing uses geopandas/shapely on the WGS84 ellipsoid
(EPSG:4326). Areas are computed geodesically (not via projection) to
avoid distortion at continental scale. For each province, instrument
layers are unioned in order of decreasing legal stringency (C10 → C50);
each cumulative geometry represents the territory covered up to and
including that instrument. Cumulative geometries are then intersected
with ecoregions to produce the province × ecoregion table. Areas at
each level are computed directly from the cumulative geometry rather
than aggregated from sub-units, which avoids monotonicity violations
that would arise from independent sub-unit accounting.

See Section 3.2 of the paper and the docstring of
`01_compute_coverage.py` for the full procedure.

---

## Data sources

| Layer | Source | Access |
|-------|--------|--------|
| Protected areas (public, private, other conserved) | Baldi et al. (2025). *Ecología Austral* 35:232–250 | [doi:10.25260/EA.25.35.2.0.2520](https://doi.org/10.25260/EA.25.35.2.0.2520) |
| Native Forests zoning (OTBN) | MAyDS — provincial ordenances 2009–2022 | Open government data |
| National Glacier Inventory (NGI) | IANIGLA (2018, updated 2023) | [glaciaresargentinos.gob.ar](https://glaciaresargentinos.gob.ar) |
| Ecoregions | Oyarzabal et al. (2018). *Ecología Austral* 28:40–63 | Open access |
| Provincial boundaries | Instituto Geográfico Nacional (IGN) | [ign.gob.ar](https://ign.gob.ar) |
| Country borders (cartographic context) | Natural Earth 10m countries | [naturalearthdata.com](https://www.naturalearthdata.com) — public domain |

---

## Citation

If you use this code or data, please cite the paper:

> González Trilla G, Baldi G, Luchetti C, Pereira P & Grimson R (2026).
> Beyond the Map: Coverage, Governance and Management of Argentina's
> Area-Based Legal Instruments for Conservation. *Oryx* (submitted).

And, if you reuse the code or processed data directly, please also cite
the code archive:

> González Trilla G, Baldi G, Luchetti C, Pereira P & Grimson R (2026).
> abli-argentina: reproduction code for Beyond the Map. Zenodo.
> doi:10.5281/zenodo.20451157

---

## License

- **Code** (`src/`): MIT — see [LICENSE](LICENSE)
- **Processed data and figures** (`data/processed/`, `output/`): CC-BY-4.0
- **Raw data** (on Zenodo): subject to the original source licenses listed above
