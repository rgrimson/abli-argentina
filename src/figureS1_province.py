#!/usr/bin/env python3
"""
figureS1_province.py
====================
Supplementary Figure S1 — Conservation coverage by province and
instrument type.

Mirror of Figure 2 (ecoregions) at the administrative-unit level.
Generates two versions:
    FigureS1_coverage_by_province.pdf/.png      (English)
    FigureS1_coverage_by_province_esp.pdf/.png  (Spanish)

Reads pct_by_province.csv (output of 01_compute_coverage.py).
Excludes the national-total row (cod_prov == "ARG").

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
        "xlabel":          "Percentage of provincial territory under legal conservation (%)",
        "aichi":           "Aichi (17%)",
        "thirtybythirty":  "30×30 (30%)",
        # Province names — keep Spanish toponyms (proper nouns), only adjust
        # accents if missing in source. The CSV typically has them correct.
        "province": {
            "Buenos Aires":          "Buenos Aires",
            "CABA":                  "Buenos Aires City",
            "Catamarca":             "Catamarca",
            "Chaco":                 "Chaco",
            "Chubut":                "Chubut",
            "Córdoba":               "Córdoba",
            "Cordoba":               "Córdoba",
            "Corrientes":            "Corrientes",
            "Entre Ríos":            "Entre Ríos",
            "Entre Rios":            "Entre Ríos",
            "Formosa":               "Formosa",
            "Jujuy":                 "Jujuy",
            "La Pampa":              "La Pampa",
            "La Rioja":              "La Rioja",
            "Mendoza":               "Mendoza",
            "Misiones":              "Misiones",
            "Neuquén":               "Neuquén",
            "Neuquen":               "Neuquén",
            "Río Negro":             "Río Negro",
            "Rio Negro":             "Río Negro",
            "Salta":                 "Salta",
            "San Juan":              "San Juan",
            "San Luis":              "San Luis",
            "Santa Cruz":            "Santa Cruz",
            "Santa Fe":              "Santa Fe",
            "Santiago del Estero":   "Santiago del Estero",
            "Tierra del Fuego":      "Tierra del Fuego",
            "Tucumán":               "Tucumán",
            "Tucuman":               "Tucumán",
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
        "xlabel":          "Porcentaje del territorio provincial bajo conservación legal (%)",
        "aichi":           "Aichi (17%)",
        "thirtybythirty":  "30×30 (30%)",
        "province": {
            "Buenos Aires":          "Buenos Aires",
            "CABA":                  "CABA",
            "Catamarca":             "Catamarca",
            "Chaco":                 "Chaco",
            "Chubut":                "Chubut",
            "Córdoba":               "Córdoba",
            "Cordoba":               "Córdoba",
            "Corrientes":            "Corrientes",
            "Entre Ríos":            "Entre Ríos",
            "Entre Rios":            "Entre Ríos",
            "Formosa":               "Formosa",
            "Jujuy":                 "Jujuy",
            "La Pampa":              "La Pampa",
            "La Rioja":              "La Rioja",
            "Mendoza":               "Mendoza",
            "Misiones":              "Misiones",
            "Neuquén":               "Neuquén",
            "Neuquen":               "Neuquén",
            "Río Negro":             "Río Negro",
            "Rio Negro":             "Río Negro",
            "Salta":                 "Salta",
            "San Juan":              "San Juan",
            "San Luis":              "San Luis",
            "Santa Cruz":            "Santa Cruz",
            "Santa Fe":              "Santa Fe",
            "Santiago del Estero":   "Santiago del Estero",
            "Tierra del Fuego":      "Tierra del Fuego",
            "Tucumán":               "Tucumán",
            "Tucuman":               "Tucumán",
        },
        "suffix": "_esp",
    },
}

# ── Colour palette + hatches (V2: mixed patterns, identical to Figure 2) ──────
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
    "C10": "",
    "C13": "",   "C16": "///",
    "C20": "",   "C23": "///",
    "C30": "",   "C40": "...", "C50": "xxx",
}


# ── Load and prepare data ─────────────────────────────────────────────────────
def load_data(locale: dict) -> pd.DataFrame:
    csv = PROC / "pct_by_province.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"Missing {csv}.\nRun 01_compute_coverage.py first."
        )
    df = pd.read_csv(csv)
    # Exclude national total row
    df = df[df["cod_prov"] != "ARG"].copy()
    df["province_display"] = (
        df["province"].map(locale["province"]).fillna(df["province"])
    )
    return df


def compute_deltas(df: pd.DataFrame) -> pd.DataFrame:
    deltas = pd.DataFrame(index=df.index)
    deltas["C10"] = df["C10"]
    for prev, curr in zip(CATS[:-1], CATS[1:]):
        deltas[curr] = (df[curr] - df[prev]).clip(lower=0)
    deltas["province_display"] = df["province_display"]
    deltas["total"]            = df["C50"]
    return deltas.sort_values("total", ascending=True)


# ── Plot ──────────────────────────────────────────────────────────────────────
def make_figure(deltas: pd.DataFrame, locale: dict):
    # Taller than Figure 2 because there are 24 provinces vs 15 ecoregions
    fig, ax = plt.subplots(figsize=(7.5, 9), facecolor="white")
    n = len(deltas)
    y_pos = np.arange(n)

    # Stacked bars
    lefts = np.zeros(n)
    for cat in CATS:
        vals = deltas[cat].values
        ax.barh(y_pos, vals, left=lefts,
                color=COLORS[cat],
                edgecolor=EDGE_COLORS[cat],
                hatch=HATCHES[cat],
                height=0.74, linewidth=0.4)
        lefts += vals

    # Reference lines
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

    # Total label
    for i, (_, row) in enumerate(deltas.iterrows()):
        ax.text(row["total"] + 0.6, i, f"{row['total']:.1f}%",
                va="center", ha="left", fontsize=7.5, color="#444444")

    # Axes
    ax.set_yticks(y_pos)
    ax.set_yticklabels(deltas["province_display"].values, fontsize=8.5)
    ax.set_xlabel(locale["xlabel"], fontsize=9)
    ax.set_xlim(0, 80)
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, linestyle=":", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    # Legend grouped by level
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

    level_prefix = locale["level_label"]("").strip()
    for text in leg.get_texts():
        if text.get_text().startswith(level_prefix):
            text.set_fontweight("bold")
            text.set_fontsize(8)

    plt.tight_layout()

    base = f"FigureS1_coverage_by_province{locale['suffix']}"
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
