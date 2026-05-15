"""
README Generator

Reads repos.csv and writes a structured, professional README.md.
Topics are grouped into categories. Each repository appears only once.

Usage:
    python update_readme.py
    python update_readme.py --csv repos.csv --readme README.md
"""

import argparse
from datetime import datetime, timezone
from typing import Dict, List

import pandas as pd


# ---------- CATEGORY MAP ----------
# Matches the order and grouping defined in crawler.py.
# Any topic not listed here falls into "Other".

TOPIC_CATEGORIES: Dict[str, List[str]] = {
    "Foundations & Core ML": [
        "machine-learning", "deep-learning", "neural-networks",
        "supervised-learning", "unsupervised-learning", "reinforcement-learning",
        "transfer-learning", "optimization-algorithms", "feature-engineering",
        "model-evaluation",
    ],
    "Frameworks & Libraries": [
        "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost",
        "lightgbm", "catboost", "huggingface-transformers", "langchain", "fastai",
    ],
    "Natural Language Processing": [
        "nlp", "text-classification", "sentiment-analysis",
        "named-entity-recognition", "question-answering",
        "translation-models", "summarization", "chatbots",
    ],
    "Generative AI & LLMs": [
        "generative-ai", "llms", "transformers",
        "attention-mechanisms", "vision-transformers",
    ],
    "Computer Vision": [
        "computer-vision", "image-classification", "object-detection",
        "image-segmentation", "image-processing", "face-recognition",
        "ocr", "pose-estimation", "gesture-recognition", "video-analytics",
    ],
    "Data Science & Analysis": [
        "data-science", "exploratory-data-analysis", "statistics",
        "data-cleaning", "pandas", "numpy", "data-visualization",
        "matplotlib", "seaborn", "plotly",
    ],
    "MLOps & Deployment": [
        "mlops", "model-deployment", "model-serving",
        "docker-for-ml", "kubernetes-ml", "airflow",
        "ci-cd", "data-pipelines",
    ],
    "Data Engineering": [
        "data-engineering", "apache-spark", "big-data",
    ],
    "Applied AI": [
        "time-series", "forecasting", "recommendation-systems",
        "anomaly-detection", "ai-in-healthcare", "ai-in-finance",
        "ai-in-education", "ai-in-manufacturing",
        "ai-in-agriculture", "ai-in-marketing",
    ],
    "Advanced Research": [
        "graph-neural-networks", "explainable-ai", "self-supervised-learning",
        "semi-supervised-learning", "meta-learning",
        "bayesian-learning", "causal-inference",
    ],
    "Robotics & Edge AI": [
        "robotics-ai", "autonomous-systems", "edge-ai", "iot-ai",
        "path-planning", "sensor-fusion", "drone-ai",
        "reinforcement-robots", "control-systems", "sim2real",
    ],
    "Developer Tools & Fundamentals": [
        "python", "sql", "r", "git", "docker",
        "api-development", "cloud-computing",
        "bash-scripting", "testing-ml",
    ],
}

# Reverse lookup: topic -> category
TOPIC_TO_CATEGORY: Dict[str, str] = {
    topic: category
    for category, topics in TOPIC_CATEGORIES.items()
    for topic in topics
}

TABLE_COLUMNS = ["Repository", "Description", "Stars", "Language", "Type", "Updated"]
MARKER_START  = "<!-- REPO_TABLE_START -->"
MARKER_END    = "<!-- REPO_TABLE_END -->"


# ---------- FORMATTING HELPERS ----------

def format_stars(stars: int) -> str:
    if stars >= 1_000:
        return f"{stars / 1000:.1f}k"
    return str(stars)


ACRONYM_OVERRIDES = {
    "nlp": "NLP", "llms": "LLMs", "ocr": "OCR", "eda": "EDA",
    "mlops": "MLOps", "api": "API", "gnn": "GNN", "iot": "IoT",
    "ci-cd": "CI/CD", "r": "R", "sql": "SQL", "aws": "AWS",
    "gcp": "GCP", "etl": "ETL", "rnn": "RNN", "cnn": "CNN",
}

def topic_to_heading(topic: str) -> str:
    if topic in ACRONYM_OVERRIDES:
        return ACRONYM_OVERRIDES[topic]
    words = topic.replace("-", " ").split()
    return " ".join(ACRONYM_OVERRIDES.get(w, w.title()) for w in words)


def anchor(text: str) -> str:
    return text.lower().replace(" ", "-").replace("&", "").replace("/", "").replace(",", "")


def build_table(rows: List[dict]) -> str:
    header = "| " + " | ".join(TABLE_COLUMNS) + " |"
    sep    = "| " + " | ".join([":---" if c != "Stars" else "---:" for c in TABLE_COLUMNS]) + " |"
    lines  = [header, sep]

    for r in rows:
        desc = (r.get("description") or "").strip()
        if len(desc) > 100:
            desc = desc[:97] + "..."

        repo_link = f"[{r['name']}]({r['url']})"
        stars     = format_stars(int(r.get("stars", 0)))
        language  = r.get("language") or "-"
        repo_type = (r.get("repo_type") or "project").replace("-", " ").title()
        updated   = r.get("last_updated") or "-"

        lines.append(
            f"| {repo_link} | {desc} | {stars} | {language} | {repo_type} | {updated} |"
        )

    return "\n".join(lines)


def build_toc(category_topic_map: Dict[str, Dict[str, List[dict]]]) -> str:
    lines = []
    for category, topics in category_topic_map.items():
        cat_anchor = anchor(category)
        lines.append(f"- [{category}](#{cat_anchor})")
        for topic in topics:
            t_anchor = anchor(topic_to_heading(topic))
            lines.append(f"  - [{topic_to_heading(topic)}](#{t_anchor})")
    return "\n".join(lines)


# ---------- MAIN ----------

def update_readme(csv_path: str = "repos.csv", readme_path: str = "README.md") -> None:
    # Load data
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"File not found: {csv_path}")
        return

    if df.empty:
        print("CSV is empty, nothing to write.")
        return

    # Deduplicate by full_name — keep highest star count if somehow duplicated
    df = df.sort_values("stars", ascending=False).drop_duplicates(subset="full_name", keep="first")

    # Assign category
    df["category"] = df["topic"].map(TOPIC_TO_CATEGORY).fillna("Other")

    # Build category -> topic -> rows map (preserving defined order)
    category_topic_map: Dict[str, Dict[str, List[dict]]] = {}

    for category, ordered_topics in TOPIC_CATEGORIES.items():
        topic_rows: Dict[str, List[dict]] = {}
        for topic in ordered_topics:
            topic_df = df[df["topic"] == topic]
            if topic_df.empty:
                continue
            topic_rows[topic] = topic_df.to_dict("records")
        if topic_rows:
            category_topic_map[category] = topic_rows

    # Handle any topics not in the category map
    uncategorized = df[df["category"] == "Other"]
    if not uncategorized.empty:
        other_map: Dict[str, List[dict]] = {}
        for topic, group in uncategorized.groupby("topic"):
            other_map[topic] = group.to_dict("records")
        if other_map:
            category_topic_map["Other"] = other_map

    # Stats
    total_repos  = len(df)
    total_topics = df["topic"].nunique()
    updated_at   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build content block
    sections = []

    # Stats line
    sections.append(
        f"**{total_repos} repositories** across **{total_topics} topics** — "
        f"last updated {updated_at}"
    )
    sections.append("")

    # Table of contents
    sections.append("## Contents")
    sections.append("")
    sections.append(build_toc(category_topic_map))
    sections.append("")
    sections.append("---")
    sections.append("")

    # Category and topic sections
    for category, topics in category_topic_map.items():
        sections.append(f"## {category}")
        sections.append("")

        for topic, rows in topics.items():
            sections.append(f"### {topic_to_heading(topic)}")
            sections.append("")
            sections.append(build_table(rows))
            sections.append("")

        sections.append("---")
        sections.append("")

    content_block = "\n".join(sections).rstrip()
    table_section = f"{MARKER_START}\n\n{content_block}\n\n{MARKER_END}"

    # Read existing README
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            readme = f.read()
    except FileNotFoundError:
        readme = _default_readme_header()

    # Replace or append
    if MARKER_START in readme and MARKER_END in readme:
        before = readme.split(MARKER_START)[0]
        after  = readme.split(MARKER_END)[1]
        new_readme = before + table_section + after
    else:
        new_readme = readme.rstrip() + "\n\n" + table_section + "\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)

    print(f"README updated: {total_repos} repos across {total_topics} topics")


def _default_readme_header() -> str:
    return """\
# AI Learning Repositories

A curated, auto-updated collection of GitHub repositories covering all areas
of artificial intelligence, machine learning, data science, and related fields.

Repositories are gathered programmatically via the GitHub API and refreshed weekly.
Each repository appears under one topic only. Results are ordered by star count.

To contribute or suggest a topic, see [CONTRIBUTE.md](CONTRIBUTE.md).

---

"""


# ---------- CLI ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate README from repos.csv")
    parser.add_argument("--csv",    default="repos.csv",  help="Path to repos CSV")
    parser.add_argument("--readme", default="README.md",  help="Path to README file")
    args = parser.parse_args()
    update_readme(csv_path=args.csv, readme_path=args.readme)
