from __future__ import annotations

from typing import BinaryIO, Dict, List

import pandas as pd


COLUMN_ALIASES = {
    "theme": ["theme", "label", "measure", "question", "statement", "item", "attribute", "parameter"],
    "metric_type": ["metric_type", "type", "metric", "measure_type"],
    "n": ["n", "base", "sample_size", "respondents", "count"],
    "mean": ["mean", "avg", "average", "mean_score"],
    "top_two_box": ["top_two_box", "top2", "top_2_box", "ttb", "top_two", "top box/top 2"],
    "low_rating": ["low_rating", "low", "bottom_two_box", "btb", "bottom2", "low_ratings"],
    "excellent": ["excellent", "excellent_pct", "top_box", "five_rating", "rating_5"],
    "promoters": ["promoters", "promoter", "promoters_pct", "promoter_pct"],
    "passives": ["passives", "passive", "passives_pct", "passive_pct"],
    "detractors": ["detractors", "detractor", "detractors_pct", "detractor_pct"],
    "score": ["score", "nps", "nps_score", "index", "confidence_score"],
    "selected_pct": ["selected_pct", "selected", "selection_pct", "pct_selected", "percentage", "%"],
    "selected_n": ["selected_n", "selected_count", "selected_base"],
}


def read_table_file(uploaded_file: BinaryIO) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Please upload a CSV or Excel table output.")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    lower_to_original = {str(col).strip().lower(): col for col in normalized.columns}
    rename_map: Dict[str, str] = {}

    for standard_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower_to_original:
                rename_map[lower_to_original[alias.lower()]] = standard_name
                break

    normalized = normalized.rename(columns=rename_map)
    return normalized


def numeric_value(row: pd.Series, column: str) -> float | None:
    if column not in row or pd.isna(row[column]):
        return None
    value = row[column]
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_theme(value: object) -> str:
    theme = str(value or "").strip()
    if not theme or theme.lower() == "nan":
        return "Table Measure"
    return " ".join(theme.split())[:80]


def infer_metric_type(row: pd.Series) -> str:
    metric = str(row.get("metric_type", "") or "").strip().lower()
    if metric:
        return metric
    if numeric_value(row, "promoters") is not None or numeric_value(row, "detractors") is not None:
        return "nps"
    if numeric_value(row, "selected_pct") is not None or numeric_value(row, "selected_n") is not None:
        return "selection"
    if numeric_value(row, "mean") is not None or numeric_value(row, "top_two_box") is not None:
        return "rating"
    return "general"


def format_n(value: float | None) -> str:
    if value is None:
        return "not specified"
    return str(int(value)) if value.is_integer() else f"{value:.0f}"


def rating_insight(insight_id: str, row: pd.Series) -> Dict[str, str]:
    theme = clean_theme(row.get("theme", "Table Measure"))
    n = numeric_value(row, "n")
    mean = numeric_value(row, "mean")
    top2 = numeric_value(row, "top_two_box")
    low = numeric_value(row, "low_rating")
    excellent = numeric_value(row, "excellent")

    if mean is not None and top2 is not None and low is not None:
        if top2 >= 65 and low < 15:
            text = f"{theme} appears to be a relative strength, with {top2:.1f}% top-two-box ratings and a mean score of {mean:.2f}/5."
        elif low >= 20 or top2 < 45:
            text = f"{theme} needs management attention, with {low:.1f}% low ratings and a mean score of {mean:.2f}/5."
        else:
            text = f"{theme} shows moderate customer confidence, with a mean score of {mean:.2f}/5 and {top2:.1f}% top-two-box ratings."
        evidence = f"{theme}: n={format_n(n)}, mean={mean:.2f}/5, top-two-box={top2:.1f}%, low ratings={low:.1f}%."
    elif mean is not None:
        text = f"{theme} records a mean score of {mean:.2f}/5, which should be reviewed alongside top-box and low-rating information if available."
        evidence = f"{theme}: n={format_n(n)}, mean={mean:.2f}/5."
    elif top2 is not None:
        text = f"{theme} records {top2:.1f}% top-two-box performance, indicating the level of positive response on this measure."
        evidence = f"{theme}: n={format_n(n)}, top-two-box={top2:.1f}%."
    else:
        text = f"{theme} is available in the table output but needs more statistics before a strong rating insight can be made."
        evidence = f"{theme}: n={format_n(n)}."

    if excellent is not None:
        evidence = evidence.rstrip(".") + f", excellent={excellent:.1f}%."

    return {"insight_id": insight_id, "theme": theme, "insight_text": text, "evidence_note": evidence}


def nps_insight(insight_id: str, row: pd.Series) -> Dict[str, str]:
    theme = clean_theme(row.get("theme", "Recommendation Advocacy"))
    n = numeric_value(row, "n")
    promoters = numeric_value(row, "promoters")
    passives = numeric_value(row, "passives")
    detractors = numeric_value(row, "detractors")
    score = numeric_value(row, "score")

    if score is None and promoters is not None and detractors is not None:
        score = promoters - detractors

    if score is not None and promoters is not None and detractors is not None:
        text = f"{theme} shows an advocacy score of {score:.1f}, with {promoters:.1f}% promoters and {detractors:.1f}% detractors."
        evidence = f"{theme}: n={format_n(n)}, promoters={promoters:.1f}%, detractors={detractors:.1f}%, score={score:.1f}%."
        if passives is not None:
            evidence = f"{theme}: n={format_n(n)}, promoters={promoters:.1f}%, passives={passives:.1f}%, detractors={detractors:.1f}%, score={score:.1f}%."
    elif score is not None:
        text = f"{theme} records an advocacy score of {score:.1f}, which should be interpreted with promoter and detractor shares if available."
        evidence = f"{theme}: n={format_n(n)}, score={score:.1f}%."
    else:
        text = f"{theme} contains advocacy information, but the table needs promoter, passive, detractor, or score fields for a stronger insight."
        evidence = f"{theme}: n={format_n(n)}."

    return {"insight_id": insight_id, "theme": theme, "insight_text": text, "evidence_note": evidence}


def selection_insight(insight_id: str, row: pd.Series) -> Dict[str, str]:
    theme = clean_theme(row.get("theme", "Selection Theme"))
    n = numeric_value(row, "n")
    selected_pct = numeric_value(row, "selected_pct")
    selected_n = numeric_value(row, "selected_n")

    if selected_pct is None and selected_n is not None and n not in (None, 0):
        selected_pct = selected_n / n * 100

    if selected_pct is None:
        text = f"{theme} is present in the table output, but selected percentage is needed to size the theme."
        evidence = f"{theme}: n={format_n(n)}."
    elif selected_pct >= 50:
        text = f"{theme} is selected by a majority of respondents at {selected_pct:.1f}%, making it a prominent table-based theme."
        evidence = f"{theme}: n={format_n(n)}, selected percentage={selected_pct:.1f}%."
    else:
        text = f"{theme} is selected by {selected_pct:.1f}% of respondents, making it a visible but not majority-level theme."
        evidence = f"{theme}: n={format_n(n)}, selected percentage={selected_pct:.1f}%."

    if selected_n is not None:
        evidence = evidence.rstrip(".") + f", selected n={format_n(selected_n)}."

    return {"insight_id": insight_id, "theme": theme, "insight_text": text, "evidence_note": evidence}


def add_table_summary_insights(insights: List[Dict[str, str]], rows: List[pd.Series], max_insights: int) -> None:
    rating_rows = []
    selection_rows = []

    for row in rows:
        metric = infer_metric_type(row)
        if metric == "rating" and numeric_value(row, "mean") is not None:
            rating_rows.append(row)
        if metric == "selection" and numeric_value(row, "selected_pct") is not None:
            selection_rows.append(row)

    def append(theme: str, text: str, evidence: str) -> None:
        if len(insights) >= max_insights:
            return
        insights.append(
            {
                "insight_id": f"TI-{len(insights) + 1:03d}",
                "theme": theme,
                "insight_text": text,
                "evidence_note": evidence,
            }
        )

    if len(rating_rows) >= 2:
        strongest = max(rating_rows, key=lambda row: numeric_value(row, "mean") or 0)
        weakest = min(rating_rows, key=lambda row: numeric_value(row, "mean") or 999)
        strong_theme = clean_theme(strongest.get("theme", "Strongest Measure"))
        weak_theme = clean_theme(weakest.get("theme", "Weakest Measure"))
        append(
            "Table Relative Strength",
            f"{strong_theme} is the strongest rated table measure, while {weak_theme} is the weakest rated measure.",
            f"{strong_theme}: mean={numeric_value(strongest, 'mean'):.2f}/5; {weak_theme}: mean={numeric_value(weakest, 'mean'):.2f}/5.",
        )

    if len(selection_rows) >= 2:
        top_rows = sorted(selection_rows, key=lambda row: numeric_value(row, "selected_pct") or 0, reverse=True)[:3]
        themes = ", ".join(clean_theme(row.get("theme", "")) for row in top_rows)
        evidence = "; ".join(
            f"{clean_theme(row.get('theme', ''))}={numeric_value(row, 'selected_pct'):.1f}%"
            for row in top_rows
        )
        append(
            "Top Table Selections",
            f"The top selected table themes are {themes}, showing where respondent attention is most concentrated.",
            evidence,
        )


def generate_insights_from_table(table_df: pd.DataFrame, max_insights: int = 25) -> pd.DataFrame:
    df = normalize_columns(table_df)
    if "theme" not in df.columns:
        raise ValueError("Table output must include a theme/label/measure/question/item column.")

    insights: List[Dict[str, str]] = []
    processed_rows: List[pd.Series] = []

    for _, row in df.iterrows():
        if len(insights) >= max_insights:
            break
        metric = infer_metric_type(row)
        insight_id = f"TI-{len(insights) + 1:03d}"
        processed_rows.append(row)

        if metric == "nps":
            insights.append(nps_insight(insight_id, row))
        elif metric == "selection":
            insights.append(selection_insight(insight_id, row))
        elif metric == "rating":
            insights.append(rating_insight(insight_id, row))
        else:
            theme = clean_theme(row.get("theme", "Table Measure"))
            insights.append(
                {
                    "insight_id": insight_id,
                    "theme": theme,
                    "insight_text": f"{theme} is present in the uploaded table, but more metric fields are needed to generate a stronger evidence-backed insight.",
                    "evidence_note": f"{theme}: insufficient recognized metric fields.",
                }
            )

    add_table_summary_insights(insights, processed_rows, max_insights)
    return pd.DataFrame(insights)
