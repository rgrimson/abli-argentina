#!/usr/bin/env python3
"""
figure1_map.py
==============
Figure 1 — Spatial distribution of Argentina's integrated conservation mosaic.

Projection: Lambert Azimuthal Equal Area (IGN official for Argentina)
+proj=laea +lat_0=-40 +lon_0=-60 +datum=WGS84

Extent: Continental Argentina only.
The Argentine Antarctic Sector and South Atlantic Islands are excluded
as they contain no area-based legal instruments of the type analysed here.

Authors
-------
    González Trilla G, Baldi G, Luchetti C, Pereira P & Grimson R (2025)
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from matplotlib_scalebar.scalebar import ScaleBar
from pyproj import CRS, Transformer
from shapely.geometry import LineString, box

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
RAW     = ROOT / "data" / "raw"
OUT     = ROOT / "output" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Projection ────────────────────────────────────────────────────────────────
LAEA = CRS.from_proj4("+proj=laea +lat_0=-40 +lon_0=-60 +datum=WGS84 +units=m")
# Inset projection: LAEA centred between Argentina and South Pole,
# handles bicontinental extent (continental SA + Antarctic sector) without
# the severe distortion that an equator-centred projection would have at
# high southern latitudes.
LAEA_SA = CRS.from_proj4("+proj=laea +lat_0=-50 +lon_0=-60 +datum=WGS84 +units=m")

# ── Level definitions ─────────────────────────────────────────────────────────
LEVELS = {
    "D": {"cat": "C50", "color": "#d5f0d5"},
    "C": {"cat": "C23", "color": "#82c785"},
    "B": {"cat": "C16", "color": "#1e8449"},
    "A": {"cat": "C10", "color": "#145a32"},
}

def get_national_percentages() -> dict:
    """
    Read national cumulative coverage from pct_by_province.csv (ARG row).
    Returns {"A": pct_A, "B": pct_B, ...} where each value is the
    cumulative percentage of continental Argentina covered up to that level.
    """
    csv = ROOT / "data" / "processed" / "pct_by_province.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"Missing {csv}. Run 01_compute_coverage.py first."
        )
    df = pd.read_csv(csv)
    arg = df[df["cod_prov"] == "ARG"].iloc[0]
    return {
        "A": float(arg["C10"]),
        "B": float(arg["C16"]),
        "C": float(arg["C23"]),
        "D": float(arg["C50"]),
    }

# ── Localised text ────────────────────────────────────────────────────────────
LOCALES = {
    "en": {
        "legend_title": "Conservation level",
        # First level shows absolute cumulative %, others show net increment
        "level_label":  lambda lv, cum, delta: (
            f"Level {lv} ({cum:.2f}%)" if lv == "A"
            else f"Level {lv} (+{delta:.2f}%)"
        ),
        "neighbours":   "Neighbouring countries",
        "unprotected":  "Not legally covered",
        "caption": (
            "Projection: Lambert Azimuthal Equal Area "
            "(IGN; lat₀=40°S, lon₀=60°W). "
            "Continental Argentina (2,780,318 km²). "
            "Antarctic Sector and South Atlantic Islands excluded."
        ),
        "suffix": "",
    },
    "es": {
        "legend_title": "Nivel de conservación",
        "level_label":  lambda lv, cum, delta: (
            f"Nivel {lv} ({cum:.2f}%)" if lv == "A"
            else f"Nivel {lv} (+{delta:.2f}%)"
        ),
        "neighbours":   "Países limítrofes",
        "unprotected":  "Sin cobertura legal",
        "caption": (
            "Proyección: Lambert Azimutal Equiárea "
            "(IGN; lat₀=40°S, lon₀=60°O). "
            "Argentina continental (2.780.318 km²). "
            "Sector Antártico e Islas del Atlántico Sur excluidos."
        ),
        "suffix": "_esp",
    },
}

PROVINCE_CODES = [
    "BA","CABA","CD","CH","CM","CS","CU","ER","FS","JJ",
    "LP","LR","MS","MZ","NQ","RN","SC","SE","SF","SJ",
    "SL","ST","TC","TF",
]

# ── Load coverage ─────────────────────────────────────────────────────────────
def load_national_coverage() -> dict:
    raw = {lv: [] for lv in LEVELS}
    for cod in PROVINCE_CODES:
        gpkg = INTERIM / f"coverage_{cod}.gpkg"
        if not gpkg.exists():
            print(f"WARNING: missing {gpkg.name} — skipping {cod}")
            continue
        gdf = gpd.read_file(gpkg)
        if "categ" not in gdf.columns:
            gdf = gdf.rename(columns={"index": "categ"})
        gdf = gdf.set_index("categ")
        for lv, info in LEVELS.items():
            cat = info["cat"]
            if cat in gdf.index:
                geom = gdf.loc[cat, "geometry"]
                if geom is not None and not geom.is_empty:
                    raw[lv].append(gpd.GeoDataFrame(
                        {"level": [lv]}, geometry=[geom], crs="EPSG:4326"
                    ))
    result = {}
    for lv, gdfs in raw.items():
        if gdfs:
            result[lv] = pd.concat(gdfs, ignore_index=True)\
                           .set_crs("EPSG:4326").to_crs(LAEA)
    return result


# ── Base cartography ──────────────────────────────────────────────────────────
def load_base_layers() -> dict:
    base = {}
    base["provinces"] = gpd.read_file(
        RAW / "provinces" / "Provincias_Continental.shp"
    ).to_crs(LAEA)
    base["continental"] = gpd.read_file(
        RAW / "provinces" / "ArgentinaContinental.shp"
    ).to_crs(LAEA)

    ne_path = RAW / "natural_earth" / "ne_10m_countries.gpkg"
    if ne_path.exists():
        world = gpd.read_file(ne_path)
        base["world"] = world
        neighbours_names = ["Chile", "Bolivia", "Paraguay", "Brazil", "Uruguay"]
        base["neighbours"] = (
            world[world["NAME"].isin(neighbours_names)].to_crs(LAEA)
        )
    else:
        print("WARNING: natural earth not found")
        base["world"] = None
        base["neighbours"] = None

    return base


# ── Map extent ────────────────────────────────────────────────────────────────
def get_extent(base):
    """
    Compute map extent with asymmetric padding:
    - ~3° extra west (Chile fully visible, room on left)
    - ~3° extra east (room for ocean, doesn't squeeze the map)
    - ~2° extra north (legend doesn't cover Misiones/Formosa)
    """
    bounds = base["provinces"].total_bounds
    pad_x  = (bounds[2] - bounds[0]) * 0.05
    pad_y  = (bounds[3] - bounds[1]) * 0.02
    extra_west  = 280_000   # ~3°
    extra_east  = 280_000   # ~3°
    extra_north = 220_000   # ~2°
    return (
        bounds[0] - pad_x - extra_west,  bounds[2] + pad_x + extra_east,
        bounds[1] - pad_y,               bounds[3] + pad_y + extra_north,
    )


# ── Graticule: draw lines and place labels at map borders ─────────────────────
def draw_graticule(ax, lats, lons, xmin, xmax, ymin, ymax):
    transformer = Transformer.from_crs("EPSG:4326", LAEA, always_xy=True)

    # Latitude lines (drawn across full lon range, clipped by axes)
    for lat in lats:
        pts = [transformer.transform(lon, lat)
               for lon in np.linspace(-78, -50, 300)]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="#bbbbbb", linewidth=0.3,
                linestyle=":", zorder=3)
        # Find where line crosses xmin (left edge) for label placement
        for i, (x, y) in enumerate(pts):
            if x >= xmin:
                ax.text(xmin, y, f"{abs(lat)}°S ",
                        ha="right", va="center",
                        fontsize=6.5, color="#555555",
                        transform=ax.transData, clip_on=False)
                break

    # Longitude lines
    for lon in lons:
        pts = [transformer.transform(lon, lat)
               for lat in np.linspace(-57, -20, 300)]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="#bbbbbb", linewidth=0.3,
                linestyle=":", zorder=3)
        # Label at top edge: find where line crosses ymax
        for i, (x, y) in enumerate(reversed(pts)):
            if y <= ymax:
                ax.text(x, ymax, f" {abs(lon)}°W",
                        ha="center", va="bottom",
                        fontsize=6.5, color="#555555",
                        transform=ax.transData, clip_on=False)
                break


# ── Main map ──────────────────────────────────────────────────────────────────
def make_map(coverage, base, locale):
    xmin, xmax, ymin, ymax = get_extent(base)

    # Figure size proportional to map aspect, with room for labels and legend
    map_w = xmax - xmin
    map_h = ymax - ymin
    aspect = map_w / map_h

    fig_h = 9.5
    fig_w = fig_h * aspect + 1.0   # extra space for labels and right margin

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="white")
    ax.set_facecolor("#d6eaf8")   # ocean

    # ── Background strategy ───────────────────────────────────────────────────
    # 1. Ocean = the axes facecolor (already set to #d6eaf8)
    # 2. All land (countries) = light gray fill
    # 3. Country borders on top
    # 4. Argentina (detailed) painted later in unprotected color, on top
    extent_geom = box(xmin, ymin, xmax, ymax)
    if base["world"] is not None:
        world_laea = base["world"].to_crs(LAEA)
        land_clipped = gpd.clip(
            world_laea,
            gpd.GeoDataFrame(geometry=[extent_geom], crs=LAEA),
        )
        # All land first (medium-light gray) — sets neighbour fill colour
        land_clipped.plot(ax=ax, color="#d8d8d8", linewidth=0, zorder=1)
        # Country borders
        land_clipped.boundary.plot(
            ax=ax, color="#999999", linewidth=0.4, zorder=2
        )

    # ── Argentina base (unprotected) ──────────────────────────────────────────
    base["continental"].plot(ax=ax, color="#f2f3f4", linewidth=0, zorder=2)

    # Malvinas and South Atlantic Islands — painted as Argentine territory
    # (Natural Earth labels these as UK; we override per IGN official cartography).
    if base["world"] is not None:
        malvinas = base["world"][
            base["world"]["NAME"].isin(["Falkland Is.", "Falkland Islands"])
        ].to_crs(LAEA)
        if len(malvinas):
            malvinas.plot(ax=ax, color="#f2f3f4",
                          edgecolor="#444444", linewidth=0.5, zorder=2)

    # ── Coverage levels D → A ─────────────────────────────────────────────────
    for lv in ["D", "C", "B", "A"]:
        if lv in coverage:
            coverage[lv].plot(ax=ax, color=LEVELS[lv]["color"],
                              linewidth=0, zorder=3)

    # ── Province boundaries ───────────────────────────────────────────────────
    base["provinces"].boundary.plot(
        ax=ax, linewidth=0.3, color="#aaaaaa", zorder=4
    )

    # ── National boundary ─────────────────────────────────────────────────────
    base["continental"].boundary.plot(
        ax=ax, linewidth=0.7, color="#444444", zorder=5
    )

    # ── Graticule ─────────────────────────────────────────────────────────────
    draw_graticule(
        ax,
        lats=[-25, -30, -35, -40, -45, -50, -55],
        lons=[-70, -65, -60, -55],
        xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax,
    )

    # ── Frame ─────────────────────────────────────────────────────────────────
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
        spine.set_edgecolor("#444444")

    # ── Legend (right side, lower-middle) ─────────────────────────────────────
    # National percentages (cumulative) and deltas (net increment per level)
    pct = get_national_percentages()
    deltas = {
        "A": pct["A"],
        "B": pct["B"] - pct["A"],
        "C": pct["C"] - pct["B"],
        "D": pct["D"] - pct["C"],
    }
    legend_elements = [
        mpatches.Patch(facecolor=LEVELS[lv]["color"],
                       edgecolor="#888888", linewidth=0.4,
                       label=locale["level_label"](lv, pct[lv], deltas[lv]))
        for lv in ["A", "B", "C", "D"]
    ]
    legend_elements.append(
        mpatches.Patch(facecolor="#f2f3f4", edgecolor="#aaaaaa",
                       linewidth=0.4, label=locale["unprotected"])
    )
    legend_elements.append(
        mpatches.Patch(facecolor="#d8d8d8", edgecolor="#999999",
                       linewidth=0.4, label=locale["neighbours"])
    )
    legend = ax.legend(
        handles=legend_elements,
        loc="upper right",
        bbox_to_anchor=(0.99, 0.99),
        fontsize=7.5,
        frameon=True, framealpha=0.95,
        edgecolor="#cccccc",
        handlelength=1.4, handleheight=1.1,
        borderpad=0.8, labelspacing=0.4,
        title=locale["legend_title"], title_fontsize=8,
    )
    legend.get_frame().set_linewidth(0.5)

    # ── Inset: South America locator (right side, lower) ──────────────────────
    if base["world"] is not None:
        # Inset placed in lower-right corner, shifted up ~5° on the main
        # map (≈ 15% of axes height) so it does not cover Malvinas.
        ax_in = inset_axes(
            ax,
            width="38%", height="28%",
            loc="lower right",
            bbox_to_anchor=(0.0, 0.15, 1.0, 1.0),
            bbox_transform=ax.transAxes,
            borderpad=0.5,
        )
        # South America + Antarctica
        sa = base["world"][
            base["world"]["CONTINENT"].isin(["South America", "Antarctica"])
        ].to_crs(LAEA_SA)
        arg = base["world"][
            base["world"]["NAME"] == "Argentina"
        ].to_crs(LAEA_SA)

        ax_in.set_facecolor("#d6eaf8")
        sa.plot(ax=ax_in, color="#e8e8e8", edgecolor="#aaaaaa", linewidth=0.3)
        arg.plot(ax=ax_in, color="#555555", edgecolor="#333333", linewidth=0.4)

        # Argentine Antarctic Sector — the LAND inside the triangular
        # sector bounded by meridians 25°W and 74°W and parallel 60°S.
        # Note: the claim is over the territory (Antarctic Peninsula and
        # adjacent land), not the ocean within the triangle.
        from shapely.geometry import Polygon
        transformer_sa = Transformer.from_crs(
            "EPSG:4326", LAEA_SA, always_xy=True
        )
        sector_pts = (
            [transformer_sa.transform(-74, lat)
             for lat in np.linspace(-60, -89.5, 60)]
          + [transformer_sa.transform(-25, lat)
             for lat in np.linspace(-89.5, -60, 60)]
          + [transformer_sa.transform(lon, -60)
             for lon in np.linspace(-25, -74, 60)]
        )
        sector_triangle = Polygon(sector_pts)

        # Intersect with the Antarctic landmass
        antarctica = base["world"][
            base["world"]["CONTINENT"] == "Antarctica"
        ].to_crs(LAEA_SA)
        if len(antarctica):
            antarctica_geom = antarctica.geometry.union_all()
            sector_land = sector_triangle.intersection(antarctica_geom)
            if not sector_land.is_empty:
                gpd.GeoDataFrame(
                    geometry=[sector_land], crs=LAEA_SA
                ).plot(
                    ax=ax_in, color="#555555", edgecolor="#333333",
                    linewidth=0.4, zorder=3,
                )

        # ── Rectangle showing main map extent (Oryx guideline) ────────────
        # Per Oryx: "inset map containing a rectangle that indicates the
        # location of the main map". Because main map and inset use
        # different projections (LAEA centred at 40°S vs LAEA centred at
        # 50°S), a straight rectangle in LAEA must be densified before
        # transforming, otherwise the borders appear straight when they
        # should curve.
        laea_to_wgs = Transformer.from_crs(LAEA, "EPSG:4326", always_xy=True)
        n_side = 50
        border_laea = (
            [(x, ymax) for x in np.linspace(xmin, xmax, n_side)]      # top
          + [(xmax, y) for y in np.linspace(ymax, ymin, n_side)]      # right
          + [(x, ymin) for x in np.linspace(xmax, xmin, n_side)]      # bottom
          + [(xmin, y) for y in np.linspace(ymin, ymax, n_side)]      # left
        )
        border_wgs = [laea_to_wgs.transform(x, y) for x, y in border_laea]
        border_sa  = [transformer_sa.transform(lon, lat)
                      for lon, lat in border_wgs]
        extent_polygon = Polygon(border_sa)
        gpd.GeoDataFrame(
            geometry=[extent_polygon], crs=LAEA_SA
        ).boundary.plot(
            ax=ax_in, color="#cc0000", linewidth=0.9, zorder=4,
        )

        # Bounds: from north Colombia (~13°N) down to the South Pole.
        corners = [
            (-82,  13),    # NW: Ecuador / Colombia coast
            (-34,  13),    # NE: northern Brazil
            (-82, -89.9),  # toward pole, western flank
            (-34, -89.9),  # toward pole, eastern flank
        ]
        xs, ys = zip(*[transformer_sa.transform(lon, lat)
                       for lon, lat in corners])
        ax_in.set_xlim(min(xs), max(xs))
        ax_in.set_ylim(min(ys), max(ys))
        ax_in.set_aspect("equal")
        ax_in.set_xticks([])
        ax_in.set_yticks([])
        for spine in ax_in.spines.values():
            spine.set_linewidth(0.5)
            spine.set_edgecolor("#888888")

    # ── Custom scale bar: 500 km, alternating segments of 100 km ──────────────
    # Layout (centred in box, lower-left corner of map):
    #   ┌─────────────────────────────┐
    #   │   ▮ ▯ ▮ ▯ ▮                 │   ← bar
    #   │   0  100  200  300  400  500│   ← tick labels
    #   │              km             │   ← unit, centred below
    #   └─────────────────────────────┘
    sb_total_km = 500
    sb_segments = 5
    sb_height_frac = 0.012
    sb_data_w = sb_total_km * 1000   # metres
    axes_w_data = xmax - xmin
    sb_w_frac = sb_data_w / axes_w_data

    # Position below the inset (lower-right). Inset bottom is at y≈0.15,
    # so the scale box goes below that. Right-aligned with the inset.
    box_width  = sb_w_frac + 0.04   # padding on each side
    box_height = 0.065
    box_right  = 0.985              # right edge aligned near map edge
    box_left   = box_right - box_width
    box_bottom = 0.025

    # The scale bar itself sits centred horizontally in the box
    sb_x_left = box_left + (box_width - sb_w_frac) / 2
    sb_y_frac = box_bottom + box_height - 0.025   # bar near top of box

    # Background box
    ax.add_patch(mpatches.Rectangle(
        (box_left, box_bottom),
        box_width, box_height,
        facecolor="white", edgecolor="#cccccc", linewidth=0.4,
        transform=ax.transAxes, zorder=9,
    ))

    # Alternating segments
    seg_w = sb_w_frac / sb_segments
    for i in range(sb_segments):
        color = "#333333" if i % 2 == 0 else "white"
        ax.add_patch(mpatches.Rectangle(
            (sb_x_left + i*seg_w, sb_y_frac),
            seg_w, sb_height_frac,
            facecolor=color, edgecolor="#333333", linewidth=0.5,
            transform=ax.transAxes, zorder=10,
        ))

    # Tick labels below the bar
    for i in range(sb_segments + 1):
        x = sb_x_left + i * seg_w
        label = f"{i * (sb_total_km // sb_segments)}"
        ax.text(x, sb_y_frac - 0.003, label,
                ha="center", va="top",
                fontsize=6, color="#333333",
                transform=ax.transAxes, zorder=11)

    # "km" centred at the bottom of the box
    ax.text(box_left + box_width/2, box_bottom + 0.005, "km",
            ha="center", va="bottom",
            fontsize=6.5, color="#333333",
            transform=ax.transAxes, zorder=11)

    # ── No north arrow: in a non-cylindrical projection (LAEA) meridians
    # are curved, so a fixed-orientation arrow would misrepresent true
    # north at most points. The graticule indicates north explicitly.

    # ── Caption ───────────────────────────────────────────────────────────────
    fig.text(
        0.5, 0.015, locale["caption"],
        ha="center", fontsize=6.5, color="#666666", style="italic",
    )

    # ── Layout: leave margin for graticule labels on left/top ─────────────────
    fig.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.05)

    base_name = f"Figure1_conservation_mosaic_map{locale['suffix']}"
    for fmt in ("pdf", "png"):
        path = OUT / f"{base_name}.{fmt}"
        plt.savefig(path, dpi=300, bbox_inches="tight", format=fmt)
        print(f"Saved: {path}")
    plt.show()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading coverage layers...")
    coverage = load_national_coverage()
    print("Loading base cartography...")
    base = load_base_layers()
    print("Rendering map...")
    for lang in ("en", "es"):
        make_map(coverage, base, LOCALES[lang])
    #make_map(coverage, base)
