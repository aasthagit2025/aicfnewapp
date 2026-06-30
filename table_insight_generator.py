from __future__ import annotations

from typing import BinaryIO, Dict, List

import pandas as pd


def read_table_file(uploaded_file: BinaryIO) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file, header=None)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file, header=None)
    raise ValueError("Please upload a CSV or Excel banner table output.")


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\n", " ").split()).strip()


def clean_theme(value: object) -> str:
    text = clean_text(value)
    if ":" in text:
        text = text.split(":", 1)[1].strip()
    for sep in [" - ", " – ", " — "]:
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    return text[:80] or "Banner Table"


def numeric_pct(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 100:
        return None
    if number <= 1.5:
        return number * 100
    return number


def find_table_starts(df: pd.DataFrame) -> List[int]:
    starts = []
    for idx, value in df.iloc[:, 0].items():
        text = clean_text(value).lower()
        if text.startswith("table "):
            starts.append(int(idx))
    return starts


def find_question_row(df: pd.DataFrame, start: int, end: int) -> int | None:
    for idx in range(start + 1, min(start + 8, end)):
        text = clean_text(df.iat[idx, 0])
        if text and not text.lower().startswith("table"):
            return idx
    return None


def find_base_row(df: pd.DataFrame, question_row: int, end: int) -> int | None:
    for idx in range(question_row + 1, min(question_row + 12, end)):
        text = clean_text(df.iat[idx, 0]).lower()
        if text.startswith("base"):
            return idx
    return None


def banner_labels(df: pd.DataFrame, question_row: int, base_row: int) -> Dict[int, str]:
    labels: Dict[int, str] = {}
    header_rows = []
    for idx in range(question_row + 1, base_row):
        row_values = [clean_text(value) for value in df.iloc[idx, 1:].tolist()]
        non_empty = [value for value in row_values if value]
        if not non_empty:
            continue
        code_like = sum(1 for value in non_empty if value.startswith("(") and value.endswith(")"))
        if code_like >= max(1, len(non_empty) // 2):
            continue
        header_rows.append(idx)

    label_row = header_rows[-1] if header_rows else None
    group_row = header_rows[-2] if len(header_rows) >= 2 else None

    current_group = ""
    for col in range(1, df.shape[1]):
        group = clean_text(df.iat[group_row, col]) if group_row is not None else ""
        if group:
            current_group = group
        label = clean_text(df.iat[label_row, col]) if label_row is not None else ""

        parts = []
        if current_group and current_group.lower() != label.lower():
            parts.append(current_group)
        if label:
            parts.append(label)
        labels[col] = " - ".join(parts) if parts else f"Column {col + 1}"

    return labels


def valid_attribute(text: str) -> bool:
    lowered = text.lower()
    if not text:
        return False
    if lowered.startswith("base") or lowered.startswith("unweighted"):
        return False
    if lowered in {"sigma", "sig", "significance"}:
        return False
    if lowered in {"1", "0"}:
        return False
    return True


def parse_table_block(df: pd.DataFrame, start: int, end: int) -> Dict[str, object] | None:
    question_row = find_question_row(df, start, end)
    if question_row is None:
        return None
    base_row = find_base_row(df, question_row, end)
    if base_row is None:
        return None

    question = clean_text(df.iat[question_row, 0])
    labels = banner_labels(df, question_row, base_row)

    rows = []
    for idx in range(base_row + 1, end):
        attribute = clean_text(df.iat[idx, 0])
        if not valid_attribute(attribute):
            continue
        values = {}
        for col, banner in labels.items():
            pct = numeric_pct(df.iat[idx, col])
            if pct is not None:
                values[banner] = pct
        if values:
            rows.append({"attribute": attribute, "values": values})

    if not rows:
        return None

    return {
        "table": clean_text(df.iat[start, 0]),
        "question": question,
        "theme": clean_theme(question),
        "rows": rows,
    }


def top_total_insight(insight_id: str, table: Dict[str, object]) -> Dict[str, str] | None:
    rows = table["rows"]
    total_candidates = []
    for row in rows:
        values = row["values"]
        total_key = next((key for key in values if key.lower().startswith("total")), None)
        if total_key:
            total_candidates.append((row["attribute"], values[total_key], total_key))
    if not total_candidates:
        return None

    attribute, pct, total_key = max(total_candidates, key=lambda item: item[1])
    theme = str(table["theme"])
    question = str(table["question"])
    return {
        "insight_id": insight_id,
        "theme": theme,
        "insight_text": f"For {theme}, {attribute} is the leading overall response at {pct:.1f}%.",
        "evidence_note": f"{table['table']} {question}: {attribute} among {total_key}={pct:.1f}%.",
    }


def standout_banner_insight(insight_id: str, table: Dict[str, object]) -> Dict[str, str] | None:
    best = None
    for row in table["rows"]:
        values = row["values"]
        total_key = next((key for key in values if key.lower().startswith("total")), None)
        total = values.get(total_key) if total_key else None
        for banner, pct in values.items():
            if total_key and banner == total_key:
                continue
            diff = pct - total if total is not None else pct
            candidate = (diff, pct, row["attribute"], banner, total)
            if best is None or candidate[0] > best[0]:
                best = candidate

    if best is None:
        return None

    diff, pct, attribute, banner, total = best
    theme = str(table["theme"])
    question = str(table["question"])
    if total is not None and abs(diff) >= 5:
        text = f"For {theme}, {banner} over-indexes on {attribute} at {pct:.1f}%, compared with {total:.1f}% overall."
        evidence = f"{table['table']} {question}: {attribute} among {banner}={pct:.1f}% vs Total={total:.1f}%."
    else:
        text = f"For {theme}, {banner} shows the strongest response on {attribute} at {pct:.1f}%."
        evidence = f"{table['table']} {question}: {attribute} among {banner}={pct:.1f}%."

    return {
        "insight_id": insight_id,
        "theme": f"{theme} by Banner",
        "insight_text": text,
        "evidence_note": evidence,
    }


def low_banner_insight(insight_id: str, table: Dict[str, object]) -> Dict[str, str] | None:
    weakest = None
    for row in table["rows"]:
        values = row["values"]
        total_key = next((key for key in values if key.lower().startswith("total")), None)
        total = values.get(total_key) if total_key else None
        if total is None:
            continue
        for banner, pct in values.items():
            if banner == total_key:
                continue
            diff = pct - total
            candidate = (diff, pct, row["attribute"], banner, total)
            if weakest is None or candidate[0] < weakest[0]:
                weakest = candidate

    if weakest is None or weakest[0] > -5:
        return None

    diff, pct, attribute, banner, total = weakest
    theme = str(table["theme"])
    question = str(table["question"])
    return {
        "insight_id": insight_id,
        "theme": f"{theme} Gap",
        "insight_text": f"For {theme}, {banner} under-indexes on {attribute} at {pct:.1f}%, compared with {total:.1f}% overall.",
        "evidence_note": f"{table['table']} {question}: {attribute} among {banner}={pct:.1f}% vs Total={total:.1f}%.",
    }


def parse_banner_tables(df: pd.DataFrame) -> List[Dict[str, object]]:
    starts = find_table_starts(df)
    tables = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(df)
        parsed = parse_table_block(df, start, end)
        if parsed:
            tables.append(parsed)
    return tables


def add_story_insights(insights: List[Dict[str, str]], tables: List[Dict[str, object]]) -> None:
    if not insights:
        return
    themes = []
    for item in insights:
        theme = item["theme"]
        if theme not in themes and "Gap" not in theme and "by Banner" not in theme:
            themes.append(theme)
        if len(themes) >= 5:
            break

    insights.append(
        {
            "insight_id": f"BT-{len(insights) + 1:03d}",
            "theme": "Overall Summary",
            "insight_text": f"Across {len(tables)} banner tables, the analysis produced {len(insights)} question-level and banner-cut insights, with early themes including {', '.join(themes)}.",
            "evidence_note": f"Based on {len(tables)} parsed banner tables and {len(insights)} generated insights.",
        }
    )
    insights.append(
        {
            "insight_id": f"BT-{len(insights) + 1:03d}",
            "theme": "Complete Story",
            "insight_text": "The banner-table story highlights the leading response patterns for each question and identifies where specific audience cuts over-index or under-index versus the total sample.",
            "evidence_note": f"Story synthesized from {len(tables)} banner tables using total responses and banner-cut comparisons.",
        }
    )


def generate_insights_from_table(table_df: pd.DataFrame) -> pd.DataFrame:
    tables = parse_banner_tables(table_df)
    insights: List[Dict[str, str]] = []

    for table in tables:
        for builder in [top_total_insight, standout_banner_insight, low_banner_insight]:
            insight = builder(f"BT-{len(insights) + 1:03d}", table)
            if insight:
                insights.append(insight)

    return pd.DataFrame(insights)
