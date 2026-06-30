from __future__ import annotations

import pandas as pd
import streamlit as st

from aicf_framework import DIMENSIONS, REQUIRED_COLUMNS, score_insight, validate_columns
from insight_generator import extract_questionnaire_text, generate_insights, read_survey_file
from story_generator import add_summary_and_story
from table_insight_generator import generate_insights_from_table, read_table_file

APP_VERSION = "AICF Streamlit Tool v4 + Flexible Tables + Review Logic Fix"

st.set_page_config(
    page_title="AICF Tool",
    page_icon="",
    layout="wide",
)


def make_template() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "insight_id": "I001",
                "theme": "Overall satisfaction",
                "insight_text": "Customers show moderate-positive satisfaction, but low-rating shares indicate improvement is still required.",
                "evidence_note": "Survey result: mean rating 3.59/5, top-two-box 59.7%, low ratings 18.4%, n=347.",
            },
            {
                "insight_id": "I002",
                "theme": "Human review example",
                "insight_text": "All customers are fully satisfied, so no improvement is required.",
                "evidence_note": "Requires validation because the claim overstates the survey evidence.",
            }
        ]
    )


def make_table_template() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["Table 1", "", "", "", ""],
            ["", "", "", "", ""],
            ["Q1: Shopping Preference", "", "", "", ""],
            ["", "", "", "", ""],
            ["", "Total", "Gender", "", "Age"],
            ["", "Total Respondents", "Male", "Female", "25-34"],
            ["Base: Total Respondents", 100, 45, 55, 40],
            ["Like shopping a lot", 0.62, 0.55, 0.70, 0.68],
            ["Shop only when needed", 0.38, 0.45, 0.30, 0.32],
        ]
    )


def score_dataframe(df: pd.DataFrame, use_manual_scores: bool = False) -> pd.DataFrame:
    results = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        try:
            scored = score_insight(row_dict, use_manual_scores=use_manual_scores)
        except TypeError:
            scored = score_insight(row_dict)
        if hasattr(scored, "__dict__"):
            results.append(scored.__dict__)
        else:
            results.append(dict(scored))
    return pd.DataFrame(results)


def summary_story_rows(report: pd.DataFrame) -> pd.DataFrame:
    if report.empty or "theme" not in report.columns:
        return pd.DataFrame()
    return report[report["theme"].isin(["Overall Summary", "Complete Story"])].copy()


st.title("AI Insight Confidence Framework")
st.caption(f"{APP_VERSION} - Generate insights from survey data or upload existing insights, then let AICF score confidence and flag human review needs.")

with st.sidebar:
    st.header("AICF Dimensions")
    for key, item in DIMENSIONS.items():
        st.write(f"**{item['label']}**")
        st.caption(f"Weight: {item['weight']:.0%}")

    template_csv = make_template().to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV Template",
        data=template_csv,
        file_name="aicf_input_template.csv",
        mime="text/csv",
    )

    table_template_csv = make_table_template().to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Banner Table Example",
        data=table_template_csv,
        file_name="aicf_banner_table_example.csv",
        mime="text/csv",
    )

mode = st.tabs(["Generate From Survey", "Generate From Tables", "Score Existing Insights"])

with mode[0]:
    st.subheader("Generate AI-Style Insights From Survey Data")
    survey_file = st.file_uploader("Upload survey data", type=["csv", "xlsx", "xls", "sav"])
    questionnaire_file = st.file_uploader("Optional: upload questionnaire", type=["docx", "txt"])

    if survey_file is None:
        st.info("Upload survey data to generate insights and evidence notes automatically.")
    else:
        try:
            survey_df, labels = read_survey_file(survey_file)
            questionnaire_text = extract_questionnaire_text(questionnaire_file)
            generated_df = generate_insights(survey_df, labels, questionnaire_text, max_insights=10000)
            generated_df = add_summary_and_story(generated_df, "survey data")
        except Exception as exc:
            st.error(f"Could not generate insights: {exc}")
            st.stop()

        if generated_df.empty:
            st.warning("No insights could be generated. Check whether the data contains rating, NPS, binary, or open-ended columns.")
            st.stop()

        st.write(f"Generated {len(generated_df)} insights from {len(survey_df)} survey rows.")
        st.dataframe(generated_df, use_container_width=True)

        generated_report = score_dataframe(generated_df, use_manual_scores=False)
        st.subheader("AICF Confidence Summary")
        generated_summary = generated_report["confidence_level"].value_counts().rename_axis("confidence_level").reset_index(name="count")

        col1, col2, col3, col4 = st.columns(4)
        levels = ["High Confidence", "Moderate Confidence", "Low-Moderate Confidence", "Low Confidence"]
        for col, level in zip([col1, col2, col3, col4], levels):
            count = int(generated_summary.loc[generated_summary["confidence_level"] == level, "count"].sum())
            col.metric(level, count)

        st.bar_chart(generated_summary.set_index("confidence_level"))
        st.subheader("Scored Generated Insights")
        st.dataframe(generated_report, use_container_width=True)

        st.download_button(
            "Download Generated Insights",
            data=generated_df.to_csv(index=False).encode("utf-8"),
            file_name="aicf_generated_insights.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download AICF Scored Report",
            data=generated_report.to_csv(index=False).encode("utf-8"),
            file_name="aicf_scored_generated_report.csv",
            mime="text/csv",
        )
        generated_story_report = summary_story_rows(generated_report)
        if not generated_story_report.empty:
            st.download_button(
                "Download Summary & Story AICF Report",
                data=generated_story_report.to_csv(index=False).encode("utf-8"),
                file_name="aicf_summary_story_report.csv",
                mime="text/csv",
            )

with mode[1]:
    st.subheader("Generate Insights From Tabulated Output")
    table_file = st.file_uploader("Upload banner table output", type=["csv", "xlsx", "xls"])

    st.caption(
        "Use MR-style banner tables where answer attributes are in rows and audience cuts/banners are in columns. "
        "The app generates question-level insights, banner-cut comparisons, an overall summary, and a complete story."
    )

    if table_file is None:
        st.info("Upload a CSV or Excel table output to generate evidence-backed insights.")
        st.dataframe(make_table_template(), use_container_width=True)
    else:
        try:
            table_df = read_table_file(table_file)
            table_insights = generate_insights_from_table(table_df)
            table_insights = add_summary_and_story(table_insights, "banner table output")
        except Exception as exc:
            st.error(f"Could not generate table insights: {exc}")
            st.stop()

        if table_insights.empty:
            st.warning("No table insights could be generated. Check whether your table has a theme/label column and metric columns.")
            st.stop()

        st.write(f"Generated {len(table_insights)} insights from uploaded table output.")
        st.dataframe(table_insights, use_container_width=True)

        table_report = score_dataframe(table_insights, use_manual_scores=False)
        st.subheader("AICF Confidence Summary")
        table_summary = table_report["confidence_level"].value_counts().rename_axis("confidence_level").reset_index(name="count")

        col1, col2, col3, col4 = st.columns(4)
        levels = ["High Confidence", "Moderate Confidence", "Low-Moderate Confidence", "Low Confidence"]
        for col, level in zip([col1, col2, col3, col4], levels):
            count = int(table_summary.loc[table_summary["confidence_level"] == level, "count"].sum())
            col.metric(level, count)

        st.bar_chart(table_summary.set_index("confidence_level"))
        st.subheader("Scored Table Insights")
        st.dataframe(table_report, use_container_width=True)

        st.download_button(
            "Download Table Insights",
            data=table_insights.to_csv(index=False).encode("utf-8"),
            file_name="aicf_table_generated_insights.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download AICF Scored Table Report",
            data=table_report.to_csv(index=False).encode("utf-8"),
            file_name="aicf_scored_table_report.csv",
            mime="text/csv",
        )
        table_story_report = summary_story_rows(table_report)
        if not table_story_report.empty:
            st.download_button(
                "Download Summary & Story AICF Report",
                data=table_story_report.to_csv(index=False).encode("utf-8"),
                file_name="aicf_table_summary_story_report.csv",
                mime="text/csv",
            )

with mode[2]:
    uploaded_file = st.file_uploader("Upload insights CSV", type=["csv"])
    use_manual_scores = st.checkbox(
        "Use manual evaluator score columns if present",
        value=False,
        help="Keep this off when you want AICF to calculate the dimension scores automatically.",
    )

    if uploaded_file is None:
        st.info("Upload a CSV with only `insight_id` and `insight_text`. You may add `evidence_note` for better scoring.")
        st.dataframe(make_template(), use_container_width=True)
    else:
        try:
            df = pd.read_csv(uploaded_file)
        except Exception as exc:
            st.error(f"Could not read the CSV file: {exc}")
            st.stop()

        missing_columns = validate_columns(list(df.columns))
        if missing_columns:
            st.error("Your CSV is missing required columns.")
            st.write(missing_columns)
            st.write("Minimum required columns:")
            st.code(", ".join(REQUIRED_COLUMNS))
            st.stop()

        try:
            report = score_dataframe(df, use_manual_scores=use_manual_scores)
        except Exception as exc:
            st.error(f"Could not score the insights: {exc}")
            st.stop()

        st.subheader("Confidence Summary")
        summary = report["confidence_level"].value_counts().rename_axis("confidence_level").reset_index(name="count")

        col1, col2, col3, col4 = st.columns(4)
        levels = ["High Confidence", "Moderate Confidence", "Low-Moderate Confidence", "Low Confidence"]
        for col, level in zip([col1, col2, col3, col4], levels):
            count = int(summary.loc[summary["confidence_level"] == level, "count"].sum())
            col.metric(level, count)

        st.bar_chart(summary.set_index("confidence_level"))

        st.subheader("Scored Insights")
        st.dataframe(report, use_container_width=True)

        csv = report.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Scored Report",
            data=csv,
            file_name="aicf_scored_report.csv",
            mime="text/csv",
        )
        uploaded_story_report = summary_story_rows(report)
        if not uploaded_story_report.empty:
            st.download_button(
                "Download Summary & Story AICF Report",
                data=uploaded_story_report.to_csv(index=False).encode("utf-8"),
                file_name="aicf_uploaded_summary_story_report.csv",
                mime="text/csv",
            )

with st.expander("How the full AICF workflow works"):
    st.write(
        "The survey module scans numeric rating columns, NPS-like columns, binary selection columns, "
        "and open-ended text columns. It creates an insight plus an evidence note, then passes both "
        "to the AICF scoring engine. This is a prototype for pilot and synopsis use; before client "
        "delivery, generated insights should still be reviewed by a researcher."
    )
