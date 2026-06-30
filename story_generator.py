from __future__ import annotations

import pandas as pd


def add_summary_and_story(insights_df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    if insights_df.empty:
        return insights_df

    insights = insights_df.to_dict("records")
    themes = []
    for item in insights:
        theme = str(item.get("theme", "")).strip()
        if theme and theme not in themes and theme not in {"Overall Summary", "Complete Story"}:
            themes.append(theme)
        if len(themes) >= 6:
            break

    attention_count = sum(
        "needs human attention" in str(item.get("insight_text", "")).lower()
        or "under-indexes" in str(item.get("insight_text", "")).lower()
        for item in insights
    )
    strength_count = sum(
        "relative strength" in str(item.get("insight_text", "")).lower()
        or "over-indexes" in str(item.get("insight_text", "")).lower()
        or "leading" in str(item.get("insight_text", "")).lower()
        for item in insights
    )

    summary = {
        "insight_id": f"SUM-{len(insights) + 1:03d}",
        "theme": "Overall Summary",
        "insight_text": (
            f"Across {source_label}, AICF generated {len(insights)} detailed insights. "
            f"The output highlights {strength_count} strength signals and {attention_count} areas needing closer review, "
            f"with key themes including {', '.join(themes[:5])}."
        ),
        "evidence_note": (
            f"Summary based on {len(insights)} generated insights from {source_label}; "
            f"strength signals={strength_count}, review signals={attention_count}."
        ),
    }

    story = {
        "insight_id": f"SUM-{len(insights) + 2:03d}",
        "theme": "Complete Story",
        "insight_text": (
            f"The overall story from {source_label} is built by combining individual question insights, "
            f"audience or response differences, and review flags so management can see what is strong, "
            f"what needs attention, and where evidence should be checked before final reporting."
        ),
        "evidence_note": f"Story synthesized from {len(insights)} generated insights and their evidence notes.",
    }

    return pd.concat([insights_df, pd.DataFrame([summary, story])], ignore_index=True)
