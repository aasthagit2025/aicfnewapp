# AI Insight Confidence Framework (AICF) Tool

This is a Streamlit app for generating and scoring AI-generated market research insights using the AI Insight Confidence Framework.

## What The Tool Does

The tool supports three workflows:

1. Upload survey data and an optional questionnaire. The tool generates AI-style insights and evidence notes, then scores them with AICF.
2. Upload tabulated output. The tool generates insights from summary tables, then scores them with AICF.
3. Upload existing AI-generated insights. The tool scores them with AICF.

The tool automatically estimates confidence across seven AICF dimensions:

- Evidence Strength
- Methodological Fit
- Triangulation / Consistency
- Interpretability
- Business Relevance
- Actionability
- Bias / Risk Control

It returns:

- Weighted confidence score
- Confidence level
- Weakest dimensions
- Recommended human review actions

## Required CSV Columns

For the "Score Existing Insights" workflow:

```text
insight_id, insight_text
```

Optional but recommended:

```text
theme, evidence_note
```

The app auto-generates the AICF dimension scores by default. If you also include manual score columns, you can choose to use them through the app checkbox:

```text
evidence_strength, methodological_fit, triangulation, interpretability, business_relevance, actionability, bias_risk
```

Manual scores should be from `1` to `5`.

## Table Output Mode

For the "Generate From Tables" workflow, upload a CSV or Excel table with columns such as:

```text
theme, metric_type, n, mean, top_two_box, low_rating, excellent, promoters, passives, detractors, score, selected_pct, selected_n
```

Supported `metric_type` values:

- `rating`
- `nps`
- `selection`

The app also accepts common aliases such as `label`, `question`, `base`, `top2`, `low`, `nps_score`, and `percentage`.

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy On Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload `app.py`, `aicf_framework.py`, `insight_generator.py`, `table_insight_generator.py`, `requirements.txt`, and `README.md`.
3. Go to Streamlit Community Cloud.
4. Select the GitHub repository.
5. Set the main file path as `app.py`.
6. Deploy.

## Suggested Pilot Use

Use this app to generate and evaluate 20 to 30 AI-generated market research insights. For the pilot, first use survey data plus questionnaire to generate insights and evidence notes, then ask 3 to 5 evaluators to review or validate the generated confidence levels.
