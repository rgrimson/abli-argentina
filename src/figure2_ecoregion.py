#!/usr/bin/env python3
"""
figure2_ecoregion.py
====================
Figure 2 — Conservation coverage by ecoregion and instrument type.

Generates two versions of the same figure:
    Figure2_coverage_by_ecoregion.pdf/.png      (English)
    Figure2_coverage_by_ecoregion_esp.pdf/.png  (Spanish)

Reads pct_by_ecoregion.csv (output of 01_compute_coverage.py) and
produces a horizontal stacked-bar plot showing the incremental
contribution of each of the eight area-based legal instruments to
total conservation coverage per ecoregion.

Bars are sorted by total coverage (descending). Dashed vertical lines
mark the Aichi Target 11 (17%) and Kunming–Montreal '30x30' (30%)
benchmarks.

Authors
-------
    González Trilla G, Baldi G, Luchetti C, Pereira P & Grimson R (2025)
"""

from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT  = ROOT / "output" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Categories ────────────────────────────────────────────────────────────────
CATS = ["C10", "C13", "C16", "C20", "C23", "C30", "C40", "C50"]

LEVEL = {
    "C10": "A",
    "C13": "B", "C16": "B",
    "C20": "C", "C23": "C",
    "C30": "D", "C40": "D", "C50": "D",
}

# ── Localised text ────────────────────────────────────────────────────────────
LOCALES = {
    "en": {
        "instrument_label": {
            "C10": "Strict PAs (IUCN I–IV)",
            "C13": "Glaciers Law",
            "C16": "Native Forests Cat. I",
            "C20": "Multi-use PAs (IUCN V–VI)",
            "C23": "Native Forests Cat. II",
            "C30": "Unclassified public PAs",
            "C40": "Private reserves",
            "C50": "Intl. designations & other",
        },
        "level_label":     lambda lv: f"Level {lv}",
        "unprotected":     "Not legally covered",
        "xlabel":          "Percentage of ecoregion territory under legal conservation (%)",
        "aichi":           "Aichi (17%)",
        "thirtybythirty":  "30×30 (30%)",
        "ecoregion": {
            "Altos Andes":                 "High Andes",
            "Bosques patagonicos":         "Patagonian Forests",
            "Chaco humedo":                "Humid Chaco",
            "Campos y Malezales":          "Campos and Malezales",
            "Chaco seco":                  "Dry Chaco",
            "Delta e islas del Parana":    "Paraná Delta and Islands",
            "Esteros del Ibera":           "Iberá Wetlands",
            "Estepa patagonica":           "Patagonian Steppe",
            "Espinal":                     "Espinal",
            "Monte de llanuras y mesetas": "Monte of Plains and Plateaus",
            "Monte de Sierras y Bolsones": "Monte of Sierras and Basins",
            "Pampa":                       "Pampas",
            "Puna":                        "Puna",
            "Selva Paranaense":            "Paranaense Forest",
            "Selva de Yungas":             "Yungas Forest",
        },
        "suffix": "",
    },
    "es": {
        "instrument_label": {
            "C10": "ÁPs estrictas (UICN I–IV)",
            "C13": "Ley de Glaciares",
            "C16": "Bosques Nativos Cat. I",
            "C20": "ÁPs de uso múltiple (UICN V–VI)",
            "C23": "Bosques Nativos Cat. II",
            "C30": "ÁPs públicas sin categorizar",
            "C40": "Reservas privadas",
            "C50": "Designaciones intl. y otras",
        },
        "level_label":     lambda lv: f"Nivel {lv}",
        "unprotected":     "Sin cobertura legal",
        "xlabel":          "Porcentaje del territorio de la ecorregión bajo conservación legal (%)",
        "aichi":           "Aichi (17%)",
        "thirtybythirty":  "30×30 (30%)",
        "ecoregion": {
            # Spanish version: clean up the unaccented CSV strings to proper
            # Spanish with accents
            "Altos Andes":                 "Altos Andes",
            "Bosques patagonicos":         "Bosques Patagónicos",
            "Chaco humedo":                "Chaco Húmedo",
            "Campos y Malezales":          "Campos y Malezales",
            "Chaco seco":                  "Chaco Seco",
            "Delta e islas del Parana":    "Delta e Islas del Paraná",
            "Esteros del Ibera":           "Esteros del Iberá",
            "Estepa patagonica":           "Estepa Patagónica",
            "Espinal":                     "Espinal",
            "Monte de llanuras y mesetas": "Monte de Llanuras y Mesetas",
            "Monte de Sierras y Bolsones": "Monte de Sierras y Bolsones",
            "Pampa":                       "Pampa",
            "Puna":                        "Puna",
            "Selva Paranaense":            "Selva Paranaense",
            "Selva de Yungas":             "Selva de Yungas",
        },
        "suffix": "_esp",
    },
}

# ── Colour palette + hatches (V2: mixed patterns) ─────────────────────────────
# Four level colours coordinated with Figure 1 map (A→D, dark→light).
LEVEL_COLOR = {
    "A": "#145a32",
    "B": "#1e8449",
    "C": "#82c785",
    "D": "#d5f0d5",
}
COLORS = {cat: LEVEL_COLOR[LEVEL[cat]] for cat in CATS}

EDGE = {
    "A": "#0b3d22",
    "B": "#155d33",
    "C": "#4e8a52",
    "D": "#88aa88",
}
EDGE_COLORS = {cat: EDGE[LEVEL[cat]] for cat in CATS}

HATCHES = {
    "C10": "",      # A: solid
    "C13": "",      # B: glaciers — solid
    "C16": "///",   # B: forests I — diagonal
    "C20": "",      # C: multi-use PAs — solid
    "C23": "///",   # C: forests II — diagonal
    "C30": "",      # D: unclassified public — solid
    "C40": "...",   # D: private — dots
    "C50": "xxx",   # D: intl. & other — cross
}

UNPROTECTED_COLOR = "#f2f3f4"


# ── Load and prepare data ─────────────────────────────────────────────────────
def load_data(locale: dict) -> pd.DataFrame:
    csv = PROC / "pct_by_ecoregion.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"Missing {csv}.\nRun 01_compute_coverage.py first."
        )
    df = pd.read_csv(csv)
    df["ecoregion_display"] = (
        df["ecoregion"].map(locale["ecoregion"]).fillna(df["ecoregion"])
    )
    return df


def compute_deltas(df: pd.DataFrame) -> pd.DataFrame:
    deltas = pd.DataFrame(index=df.index)
    deltas["C10"] = df["C10"]
    for prev, curr in zip(CATS[:-1], CATS[1:]):
        deltas[curr] = (df[curr] - df[prev]).clip(lower=0)
    deltas["unprotected"]       = (100 - df["C50"]).clip(lower=0)
    deltas["ecoregion_display"] = df["ecoregion_display"]
    deltas["total"]             = df["C50"]
    return deltas.sort_values("total", ascending=True)


# ── Plot ──────────────────────────────────────────────────────────────────────
def make_figure(deltas: pd.DataFrame, locale: dict):
    fig, ax = plt.subplots(figsize=(7.5, 6.5), facecolor="white")
    n = len(deltas)
    y_pos = np.arange(n)

    # ── Stacked bars ──────────────────────────────────────────────────────────
    lefts = np.zeros(n)
    for cat in CATS:
        vals = deltas[cat].values
        ax.barh(y_pos, vals, left=lefts,
                color=COLORS[cat],
                edgecolor=EDGE_COLORS[cat],
                hatch=HATCHES[cat],
                height=0.74, linewidth=0.4)
        lefts += vals

    # ── Reference lines ───────────────────────────────────────────────────────
    ax.axvline(17, color="#c0392b", linestyle="--",
               linewidth=1.1, alpha=0.85, zorder=5)
    ax.axvline(30, color="#27ae60", linestyle="--",
               linewidth=1.1, alpha=0.85, zorder=5)
    ax.text(17, n - 0.3, locale["aichi"],
            color="#c0392b", fontsize=7, ha="center", va="bottom",
            bbox=dict(facecolor="white", edgecolor="none",
                      pad=1.2, alpha=0.85))
    ax.text(30, n - 0.3, locale["thirtybythirty"],
            color="#27ae60", fontsize=7, ha="center", va="bottom",
            bbox=dict(facecolor="white", edgecolor="none",
                      pad=1.2, alpha=0.85))

    # ── Total labels ──────────────────────────────────────────────────────────
    for i, (_, row) in enumerate(deltas.iterrows()):
        ax.text(row["total"] + 0.6, i, f"{row['total']:.1f}%",
                va="center", ha="left", fontsize=7.5, color="#444444")

    # ── Axes ─────────────────────────────────────────────────────────────────
    ax.set_yticks(y_pos)
    ax.set_yticklabels(deltas["ecoregion_display"].values, fontsize=8.5)
    ax.set_xlabel(locale["xlabel"], fontsize=9)
    ax.set_xlim(0, 80)
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, linestyle=":", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    # ── Legend grouped by level ──────────────────────────────────────────────
    legend_handles = []
    prev_level = None
    for cat in CATS:
        lv = LEVEL[cat]
        if lv != prev_level:
            legend_handles.append(
                mpatches.Patch(visible=False, label=locale["level_label"](lv))
            )
            prev_level = lv
        legend_handles.append(
            mpatches.Patch(facecolor=COLORS[cat],
                           edgecolor=EDGE_COLORS[cat],
                           hatch=HATCHES[cat],
                           linewidth=0.4,
                           label=locale["instrument_label"][cat])
        )
    leg = ax.legend(
        handles=legend_handles,
        loc="lower left",
        bbox_to_anchor=(0.65, 0.01),
        fontsize=7.5,
        frameon=True, framealpha=0.95,
        edgecolor="#cccccc",
        handlelength=1.4, handleheight=1.0,
        borderpad=0.8, labelspacing=0.4,
        title_fontsize=8,
    )
    leg.get_frame().set_linewidth(0.5)

    # Bold "Level X" / "Nivel X" headers
    level_prefix = locale["level_label"]("").strip()   # e.g. "Level" or "Nivel"
    for text in leg.get_texts():
        if text.get_text().startswith(level_prefix):
            text.set_fontweight("bold")
            text.set_fontsize(8)

    plt.tight_layout()

    base = f"Figure2_coverage_by_ecoregion{locale['suffix']}"
    for fmt in ("pdf", "png"):
        path = OUT / f"{base}.{fmt}"
        plt.savefig(path, dpi=300, bbox_inches="tight", format=fmt)
        print(f"Saved: {path}")
    plt.show()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    for lang in ("en", "es"):
        locale = LOCALES[lang]
        print(f"--- Rendering language: {lang} ---")
        df     = load_data(locale)
        deltas = compute_deltas(df)
        make_figure(deltas, locale)
    print("All done.")