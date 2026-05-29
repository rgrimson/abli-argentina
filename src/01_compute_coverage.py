#!/usr/bin/env python3
"""
01_compute_coverage.py
======================
Computes cumulative conservation coverage for continental Argentina
across eight nested instrument categories (C10–C50), disaggregated
by province and ecoregion.

Instrument categories (cumulative nested union)
------------------------------------------------
C10  Strict protected areas (IUCN I–IV)
C13  + Glaciers Law (Law 26.639 / National Glacier Inventory)
C16  + Native Forests Category I (OTBN Cat. I)
C20  + Multi-use protected areas (IUCN V–VI)
C23  + Native Forests Category II (OTBN Cat. II)
C30  + Unclassified public protected areas
C40  + Private reserves
C50  + International designations and other conserved areas

Input data
----------
All raw shapefiles must be placed under data/raw/ as described in
README.md. Intermediate GeoPackage files are written to data/interim/
and final CSV tables to data/processed/.

Usage
-----
    python src/01_compute_coverage.py

Run from the repo root. Re-runs skip completed steps unless --force is
passed.

Authors
-------
    rgrimson  (original calcular_superficies.py)
    [coauthors]
"""

import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parents[1]
RAW      = ROOT / "data" / "raw"
INTERIM  = ROOT / "data" / "interim"
PROC     = ROOT / "data" / "processed"

for d in (INTERIM, PROC):
    d.mkdir(parents=True, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
CATS = ["C10", "C13", "C16", "C20", "C23", "C30", "C40", "C50"]

# Province codes → names (alphabetical by code)
PROVINCES = {
    "BA":   "Buenos Aires",
    "CABA": "CABA",
    "CD":   "Córdoba",
    "CH":   "Chaco",
    "CM":   "Catamarca",
    "CS":   "Corrientes",
    "CU":   "Chubut",
    "ER":   "Entre Ríos",
    "FS":   "Formosa",
    "JJ":   "Jujuy",
    "LP":   "La Pampa",
    "LR":   "La Rioja",
    "MS":   "Misiones",
    "MZ":   "Mendoza",
    "NQ":   "Neuquén",
    "RN":   "Río Negro",
    "SC":   "Santa Cruz",
    "SE":   "Santiago del Estero",
    "SF":   "Santa Fe",
    "SJ":   "San Juan",
    "SL":   "San Luis",
    "ST":   "Salta",
    "TC":   "Tucumán",
    "TF":   "Tierra del Fuego",
}

# Province code → year of current OTBN ordenance
OTBN_YEAR = {
    "CABA": 1994, "BA": 2016, "CD": 2010, "CH": 2009, "CM": 2010,
    "CS":   2010, "CU": 2010, "ER": 2014, "FS": 2018, "JJ": 2018,
    "LP":   2011, "LR": 2015, "MS": 2017, "MZ": 2010, "NQ": 2011,
    "RN":   2010, "SC": 2022, "SE": 2015, "SF": 2022, "SJ": 2016,
    "SL":   2012, "ST": 2009, "TC": 2010, "TF": 2022,
}

# OTBN conservation category → instrument code
OTBN_CAT = {"I": "C16", "II": "C23", "III": "C999"}

# IUCN category → instrument code
def iucn_to_cat(value):
    if pd.isna(value):
        return "C30"
    v = str(value).strip().upper()
    if v in {"I", "IA", "IB", "II", "III", "IV"}:
        return "C10"
    if v in {"V", "VI"}:
        return "C20"
    return "C30"

# ── Geodesy ───────────────────────────────────────────────────────────────────
_geod = Geod(ellps="WGS84")

def ellipsoidal_area_km2(geom) -> float:
    """
    Ellipsoidal area (WGS84) in km² for any polygon-like geometry.

    Robust against GeometryCollection: unary_union of complex inputs may
    produce a GeometryCollection containing both polygons and spurious
    line/point fragments at edges. This function sums areas of the polygon
    parts and ignores zero-dimensional components.
    """
    if geom is None or geom.is_empty:
        return 0.0
    if geom.geom_type == "Polygon":
        area, _ = _geod.geometry_area_perimeter(geom)
        return abs(area) / 1e6
    if geom.geom_type == "MultiPolygon":
        return sum(abs(_geod.geometry_area_perimeter(p)[0])
                   for p in geom.geoms) / 1e6
    if geom.geom_type == "GeometryCollection":
        return sum(ellipsoidal_area_km2(g) for g in geom.geoms)
    # Point, LineString, etc. → zero area
    return 0.0

# ── Geometry utilities ────────────────────────────────────────────────────────
def _keep_polygons(geom):
    """Return only polygon/multipolygon parts from any geometry."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        parts = [
            g for g in geom.geoms
            if g.geom_type in ("Polygon", "MultiPolygon")
        ]
        if not parts:
            return None
        return unary_union(parts)
    return None


def _repair(geom):
    """Attempt to repair an invalid geometry."""
    try:
        fixed = make_valid(geom)
        return _keep_polygons(fixed)
    except Exception:
        return None


def validate_and_repair(gdf: gpd.GeoDataFrame, name: str = "") -> gpd.GeoDataFrame:
    """
    Ensure a GeoDataFrame is in WGS84 and has valid geometries.
    Repairs in place where possible; drops unrecoverable rows.
    """
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        log.warning("%s: reprojecting from %s → EPSG:4326", name, gdf.crs)
        gdf = gdf.to_crs("EPSG:4326")

    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        log.info("%s: %d invalid geometries — attempting buffer(0) repair", name, invalid.sum())
        gdf.geometry = gdf.geometry.buffer(0)
        still_invalid = ~gdf.geometry.is_valid
        if still_invalid.any():
            log.info("%s: %d remaining — applying make_valid", name, still_invalid.sum())
            gdf.loc[still_invalid, "geometry"] = (
                gdf.loc[still_invalid, "geometry"].apply(_repair)
            )
        n_dropped = gdf.geometry.isna().sum() + (~gdf.geometry.is_valid).sum()
        if n_dropped:
            log.warning("%s: dropping %d unrecoverable geometries", name, n_dropped)
            gdf = gdf[gdf.geometry.notna() & gdf.geometry.is_valid]

    log.info("%s: %d features, CRS=EPSG:4326, all valid", name, len(gdf))
    return gdf


def read_validated(path: Path, name: str = "") -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, force_2d=True)
    return validate_and_repair(gdf, name or path.name)


def enforce_monotonicity(df: pd.DataFrame, cats: list = CATS) -> pd.DataFrame:
    """
    Ensure that for every row, cat[i] >= cat[i-1].
    Cumulative coverage must be non-decreasing by construction
    (each Cx = Cx-1 ∪ new_layer ≥ Cx-1). Violations indicate
    GIS processing artefacts; they are corrected here and logged.
    """
    df = df.copy()
    for col_prev, col_next in zip(cats[:-1], cats[1:]):
        mask = df[col_next] < df[col_prev]
        if mask.any():
            log.warning(
                "Monotonicity violation %s > %s in %d row(s): %s — correcting",
                col_prev, col_next, mask.sum(),
                list(df.index[mask]),
            )
            df.loc[mask, col_next] = df.loc[mask, col_prev]
    return df


# ── Phase 0: Load and prepare input layers ────────────────────────────────────
def load_inputs():
    """
    Load all input spatial layers. Returns a dict of GeoDataFrames.
    Each layer has a 'gr_categ' column with the instrument code.
    """
    log.info("=== Phase 0: Loading input layers ===")
    layers = {}

    # Provinces
    layers["provinces"] = read_validated(
        RAW / "provinces" / "Provincias_Continental.shp", "Provinces"
    )
    layers["provinces"].set_index("Provincia", inplace=True)
    layers["provinces"]["area_km2"] = (
        layers["provinces"].geometry.apply(ellipsoidal_area_km2)
    )

    # Continental boundary
    arg_cont = read_validated(
        RAW / "provinces" / "ArgentinaContinental.shp", "ArgentinaContinental"
    )
    layers["arg_boundary"] = arg_cont.geometry.union_all()

    # Ecoregions
    ecor_path = INTERIM / "ecoregions_paper.gpkg"
    if ecor_path.exists():
        gdf_ecor = read_validated(ecor_path, "Ecoregions (cached)")
    else:
        gdf_ecor = read_validated(
            RAW / "ecoregions" / "Ecoregiones-ajustado.shp", "Ecoregions (raw)"
        )
        gdf_ecor = gdf_ecor.clip(layers["arg_boundary"])
        gdf_ecor["area_km2"] = gdf_ecor.geometry.apply(ellipsoidal_area_km2)
        # Generate short codes from names
        def _gen_code(name):
            parts = name.split()
            if len(parts) == 1:
                return parts[0][:3].upper()
            return "".join(w[0].upper() for w in parts if len(w) > 3)
        gdf_ecor["cod"] = [_gen_code(n) for n in gdf_ecor["ECOREGION"]]
        gdf_ecor.set_index("cod", inplace=True)
        gdf_ecor.to_file(ecor_path, driver="GPKG")
        log.info("Ecoregions cached → %s", ecor_path)
    layers["ecoregions"] = gdf_ecor

    # Glaciers (National Glacier Inventory)
    glac_path = INTERIM / "glaciers_repaired.gpkg"
    if glac_path.exists():
        gdf_glac = read_validated(glac_path, "Glaciers (cached)")
    else:
        gdf_glac = read_validated(
            RAW / "glaciers" / "ING-Argentina.shp", "Glaciers (raw)"
        )
        gdf_glac["gr_categ"] = "C13"
        gdf_glac.to_file(glac_path, driver="GPKG")
    gdf_glac["gr_categ"] = "C13"
    layers["glaciers"] = gdf_glac

    # Public protected areas
    pub_path = INTERIM / "public_pas_continental.gpkg"
    if pub_path.exists():
        gdf_pub = read_validated(pub_path, "Public PAs (cached)")
    else:
        gdf_pub = read_validated(
            RAW / "protected_areas" / "ProteccionPublica.shp", "Public PAs (raw)"
        )
        gdf_pub["gr_categ"] = gdf_pub["IUCN"].apply(iucn_to_cat)
        gdf_pub = gdf_pub.clip(layers["arg_boundary"])
        gdf_pub.to_file(pub_path, driver="GPKG")
    layers["public_pas"] = gdf_pub

    # Private protected areas
    priv_path = INTERIM / "private_pas_continental.gpkg"
    if priv_path.exists():
        gdf_priv = read_validated(priv_path, "Private PAs (cached)")
    else:
        gdf_priv = read_validated(
            RAW / "protected_areas" / "PROT_PRIVADA.shp", "Private PAs (raw)"
        )
        gdf_priv["gr_categ"] = "C40"
        gdf_priv = gdf_priv.clip(layers["arg_boundary"])
        gdf_priv.to_file(priv_path, driver="GPKG")
    layers["private_pas"] = gdf_priv

    # Other conserved areas
    oai_path = INTERIM / "other_conserved_continental.gpkg"
    if oai_path.exists():
        gdf_oai = read_validated(oai_path, "Other conserved areas (cached)")
    else:
        gdf_oai = read_validated(
            RAW / "protected_areas" / "AreasConservadas.shp", "Other conserved areas (raw)"
        )
        gdf_oai["gr_categ"] = "C50"
        gdf_oai = gdf_oai.clip(layers["arg_boundary"])
        gdf_oai.to_file(oai_path, driver="GPKG")
    layers["other_conserved"] = gdf_oai

    return layers


def load_otbn(cod: str) -> gpd.GeoDataFrame:
    """
    Load the OTBN shapefile for a province and dissolve by conservation
    category. Dissolving before any spatial operation reduces feature count
    from potentially tens of thousands of individual polygons to 2-3
    dissolved geometries (Cat I, II, III), which dramatically speeds up
    subsequent clip and union operations.
    """
    yr   = OTBN_YEAR[cod]
    name = f"{cod}_{yr}_OTBN"
    rep  = RAW / "native_forests" / name / f"{name}_rep.shp"
    raw  = RAW / "native_forests" / name / f"{name}.shp"
    path = rep if rep.exists() else raw
    gdf  = read_validated(path, f"OTBN {cod}")
    gdf["gr_categ"] = gdf["Cat_cons"].map(OTBN_CAT)
    # Dissolve by category: many polygons → one geometry per category
    gdf = gdf[gdf["gr_categ"].notna()].dissolve(by="gr_categ").reset_index()
    # Validate after dissolve — complex boundaries can produce invalid results
    gdf = validate_and_repair(gdf, f"OTBN {cod} (dissolved)")
    log.info("OTBN %s: dissolved to %d category geometries", cod, len(gdf))
    return gdf


# ── Phase 1: Per-province cumulative coverage ─────────────────────────────────
def build_province_coverage(cod: str, layers: dict) -> gpd.GeoDataFrame:
    """
    For one province, build the 8-level cumulative union geometry.

    Returns a GeoDataFrame indexed by category code (C10…C50) with columns:
        geometry, area_km2, cod_prov
    """
    prov = PROVINCES[cod]
    log.info("Province %s (%s)", cod, prov)

    prov_geom = layers["provinces"].loc[prov, "geometry"]

    # Clip all national layers to this province
    gdf_pub   = layers["public_pas"].clip(prov_geom)
    gdf_glac  = layers["glaciers"].clip(prov_geom)
    gdf_priv  = layers["private_pas"].clip(prov_geom)
    gdf_oai   = layers["other_conserved"].clip(prov_geom)
    gdf_otbn  = load_otbn(cod).clip(prov_geom)

    # Merge all layers into one GeoDataFrame
    pieces = [gdf_pub, gdf_glac, gdf_priv, gdf_oai, gdf_otbn]
    all_layers = pd.concat(
        [p[["gr_categ", "geometry"]] for p in pieces if len(p) > 0],
        ignore_index=True,
    )
    all_layers = all_layers[
        all_layers.geometry.notna()
        & ~all_layers.geometry.is_empty
        & all_layers.geometry.is_valid
    ]
    # Dissolve by category before the union loop: reduces feature count
    # from potentially hundreds of individual PAs to one geometry per
    # category, making the cumulative union much faster.
    all_layers = (
        all_layers.dissolve(by="gr_categ")
        .reset_index()[["gr_categ", "geometry"]]
    )

    # Build cumulative union: each Cx = union of all layers with cat <= Cx
    cumulative_geom = None
    rows = []
    for cat in CATS:
        mask = all_layers["gr_categ"] == cat
        if mask.any():
            new_geom = all_layers.loc[mask, "geometry"].union_all()
            cumulative_geom = (
                unary_union([cumulative_geom, new_geom])
                if cumulative_geom is not None
                else new_geom
            )
        if cumulative_geom is not None:
            # Clean geometry: extract polygon parts from any GeometryCollection
            # (unary_union can produce spurious LineStrings at edges).
            cumulative_geom = _keep_polygons(cumulative_geom) or cumulative_geom
            rows.append({
                "categ":    cat,
                "geometry": cumulative_geom,
                "area_km2": ellipsoidal_area_km2(cumulative_geom),
                "cod_prov": cod,
            })

    return gpd.GeoDataFrame(rows, crs="EPSG:4326").set_index("categ")


def run_province_coverage(layers: dict, force: bool = False):
    """Build or load per-province coverage GeoPackages."""
    log.info("=== Phase 1: Per-province coverage ===")
    for cod in PROVINCES:
        out = INTERIM / f"coverage_{cod}.gpkg"
        if out.exists() and not force:
            log.info("  %s — cached, skipping", cod)
            continue
        gdf = build_province_coverage(cod, layers)
        gdf.to_file(out, driver="GPKG")
        log.info("  %s — saved (%d categories)", cod, len(gdf))


# ── Phase 2: Province × ecoregion intersection ────────────────────────────────
def build_prov_ecor_coverage(cod: str, layers: dict) -> gpd.GeoDataFrame:
    """
    Intersect per-province cumulative coverage with ecoregions.

    Returns rows of (cod_prov, cod_ecor, categ, area_km2).
    """
    prov = PROVINCES[cod]
    prov_geom = layers["provinces"].loc[prov, "geometry"]

    # Load cached province coverage
    gdf_prov = gpd.read_file(INTERIM / f"coverage_{cod}.gpkg")
    if "categ" not in gdf_prov.columns:
        gdf_prov = gdf_prov.rename(columns={"index": "categ"})
    gdf_prov = gdf_prov.set_index("categ")

    # Ecoregions that overlap with this province
    ecors = layers["ecoregions"][
        layers["ecoregions"].intersects(prov_geom)
    ]

    rows = []
    for ecor_cod, ecor_row in ecors.iterrows():
        ecor_geom = ecor_row.geometry
        for cat in CATS:
            if cat not in gdf_prov.index:
                continue
            intersection = _keep_polygons(
                gdf_prov.loc[cat, "geometry"].intersection(ecor_geom)
            )
            if intersection is None or intersection.is_empty:
                continue
            rows.append({
                "cod_prov": cod,
                "cod_ecor": ecor_cod,
                "categ":    cat,
                "area_km2": ellipsoidal_area_km2(intersection),
            })

    return pd.DataFrame(rows)


def run_prov_ecor_coverage(layers: dict, force: bool = False):
    """Build or load province × ecoregion intersection tables."""
    log.info("=== Phase 2: Province × ecoregion intersection ===")
    for cod in PROVINCES:
        out = INTERIM / f"coverage_ecor_{cod}.csv"
        if out.exists() and not force:
            log.info("  %s — cached, skipping", cod)
            continue
        df = build_prov_ecor_coverage(cod, layers)
        df.to_csv(out, index=False)
        log.info("  %s — %d rows", cod, len(df))


# ── Phase 3: Build summary tables ─────────────────────────────────────────────
def build_tables(layers: dict):
    """
    Read all interim outputs and produce the final CSV tables.

    Outputs (in data/processed/)
    -----------------------------
    areas_by_province.csv           km² per province per category
    pct_by_province.csv             % of provincial area
    areas_by_ecoregion.csv          km² per ecoregion per category
    pct_by_ecoregion.csv            % of ecoregion area
    areas_by_province_ecoregion.csv km² per province×ecoregion per category
    pct_by_province_ecoregion.csv   % of province×ecoregion area
    """
    log.info("=== Phase 3: Building summary tables ===")

    gdf_prov = layers["provinces"]
    gdf_ecor = layers["ecoregions"]

    # ── 3a. By province ───────────────────────────────────────────────────────
    rows_prov = []
    for cod in PROVINCES:
        prov = PROVINCES[cod]
        sup_prov = gdf_prov.loc[prov, "area_km2"]
        gpkg = INTERIM / f"coverage_{cod}.gpkg"
        if not gpkg.exists():
            log.warning("Missing %s — skipping", gpkg)
            continue
        gdf = gpd.read_file(gpkg)
        if "categ" not in gdf.columns:
            gdf = gdf.rename(columns={"index": "categ"})
        gdf = gdf.set_index("categ")
        # Recompute area from geometry to bypass any buggy stored area_km2.
        # Cleans GeometryCollections via _keep_polygons before measuring.
        row = {"cod_prov": cod, "province": prov, "area_km2": sup_prov}
        for cat in CATS:
            if cat in gdf.index:
                # ellipsoidal_area_km2 handles GeometryCollection by
                # summing polygon parts — no unary_union needed.
                row[cat] = ellipsoidal_area_km2(gdf.loc[cat, "geometry"])
            else:
                row[cat] = 0.0
        rows_prov.append(row)

    df_areas_prov = pd.DataFrame(rows_prov).set_index("cod_prov")
    df_areas_prov = enforce_monotonicity(df_areas_prov)
    # National total
    nat = df_areas_prov[CATS + ["area_km2"]].sum()
    nat["province"] = "Argentina (continental)"
    nat["cod_prov"] = "ARG"
    df_areas_prov.loc["ARG"] = nat

    df_pct_prov = df_areas_prov[["province", "area_km2"]].copy()
    for cat in CATS:
        df_pct_prov[cat] = (
            df_areas_prov[cat] / df_areas_prov["area_km2"] * 100
        ).round(4)

    df_areas_prov.to_csv(PROC / "areas_by_province.csv", float_format="%.4f")
    df_pct_prov.to_csv(PROC / "pct_by_province.csv",   float_format="%.4f")
    log.info("Saved: areas_by_province.csv, pct_by_province.csv")

    # ── 3b. By province × ecoregion ───────────────────────────────────────────
    dfs = []
    for cod in PROVINCES:
        csv = INTERIM / f"coverage_ecor_{cod}.csv"
        if not csv.exists():
            log.warning("Missing %s — skipping", csv)
            continue
        dfs.append(pd.read_csv(csv))

    df_long = pd.concat(dfs, ignore_index=True)

    # Pivot to wide format: index=(cod_prov, cod_ecor), columns=CATS
    df_wide = (
        df_long.pivot_table(
            index=["cod_prov", "cod_ecor"],
            columns="categ",
            values="area_km2",
            aggfunc="sum",
        )
        .reindex(columns=CATS)
        .fillna(0.0)
        .reset_index()
    )

    # Add metadata
    df_wide["province"] = df_wide["cod_prov"].map(PROVINCES)
    df_wide["ecoregion"] = df_wide["cod_ecor"].map(
        gdf_ecor["ECOREGION"].to_dict()
    )
    df_wide["area_province_km2"] = df_wide["cod_prov"].map(
        gdf_prov["area_km2"].to_dict()
    )
    df_wide["area_ecoregion_km2"] = df_wide["cod_ecor"].map(
        gdf_ecor["area_km2"].to_dict()
    )
    # Province×ecoregion area: intersection
    def _prov_ecor_area(row):
        prov_g = gdf_prov.loc[PROVINCES[row["cod_prov"]], "geometry"]
        ecor_g = gdf_ecor.loc[row["cod_ecor"], "geometry"]
        return ellipsoidal_area_km2(prov_g.intersection(ecor_g))

    df_wide["area_prov_ecor_km2"] = df_wide.apply(_prov_ecor_area, axis=1)
    df_wide = enforce_monotonicity(df_wide)

    col_order = (
        ["cod_prov", "province", "cod_ecor", "ecoregion",
         "area_province_km2", "area_ecoregion_km2", "area_prov_ecor_km2"]
        + CATS
    )
    df_wide = df_wide[col_order].set_index(["cod_prov", "cod_ecor"])

    df_pct_pe = df_wide[
        ["province", "ecoregion",
         "area_province_km2", "area_ecoregion_km2", "area_prov_ecor_km2"]
    ].copy()
    for cat in CATS:
        df_pct_pe[cat] = (
            df_wide[cat] / df_wide["area_prov_ecor_km2"] * 100
        ).round(4)

    df_wide.to_csv(PROC / "areas_by_province_ecoregion.csv", float_format="%.4f")
    df_pct_pe.to_csv(PROC  / "pct_by_province_ecoregion.csv", float_format="%.4f")
    log.info("Saved: areas_by_province_ecoregion.csv, pct_by_province_ecoregion.csv")

    # ── 3c. By ecoregion (aggregate across provinces) ─────────────────────────
    df_areas_ecor = (
        df_wide[CATS + ["area_prov_ecor_km2"]]
        .groupby("cod_ecor")
        .sum()
        .rename(columns={"area_prov_ecor_km2": "area_km2"})
    )
    df_areas_ecor["ecoregion"] = df_areas_ecor.index.map(
        gdf_ecor["ECOREGION"].to_dict()
    )
    df_areas_ecor = enforce_monotonicity(df_areas_ecor)

    df_pct_ecor = df_areas_ecor[["ecoregion", "area_km2"]].copy()
    for cat in CATS:
        df_pct_ecor[cat] = (
            df_areas_ecor[cat] / df_areas_ecor["area_km2"] * 100
        ).round(4)

    df_areas_ecor.to_csv(PROC / "areas_by_ecoregion.csv", float_format="%.4f")
    df_pct_ecor.to_csv(PROC  / "pct_by_ecoregion.csv",   float_format="%.4f")
    log.info("Saved: areas_by_ecoregion.csv, pct_by_ecoregion.csv")

    log.info("=== All tables written to %s ===", PROC)


# ── Entry point ───────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--force", action="store_true",
        help="Recompute all steps even if cached outputs exist.",
    )
    p.add_argument(
        "--phase", type=int, choices=[0, 1, 2, 3], default=None,
        help="Run only a specific phase (0=load, 1=province, 2=ecor, 3=tables).",
    )
    return p.parse_args()


def main():
    args = parse_args()

    layers = load_inputs()                              # always needed

    if args.phase is None or args.phase == 1:
        run_province_coverage(layers, force=args.force)

    if args.phase is None or args.phase == 2:
        run_prov_ecor_coverage(layers, force=args.force)

    if args.phase is None or args.phase == 3:
        build_tables(layers)


if __name__ == "__main__":
    main()