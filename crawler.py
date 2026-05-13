"""
AI Learning Repository Crawler

Crawls GitHub for high-quality AI/ML/Data Science learning repositories
across 90+ topics. Saves results to repos.csv with deduplication across topics.

Changes from v1:
- Removed email scraping 
- Global deduplication: each repo appears under one topic only
- No README fetching
- Dynamic top-K per topic
- Richer metadata: language, last_updated, license, repo_type
- Uses GITHUB_TOKEN env var automatically 
- Respects rate limits with proper backoff
"""

import os
import re
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Set

import requests
import pandas as pd

# ---------- CONFIG ----------
GITHUB_API_SEARCH = "https://api.github.com/search/repositories"

TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github+json, application/vnd.github.mercy-preview+json"
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

PER_PAGE = 50
TOP_K = 7            # Top repos to keep per topic
MIN_STARS = 5        # Absolute noise floor only — does not override top-K logic


# ---------- TOPIC CATEGORIES ----------
# Topics are grouped into categories used by update_readme.py.
# A repo is assigned to the first topic that claims it (global dedup).
# Order within each category determines priority.

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
        "bash-scripting", "testing-ml", "ci-cd",
    ],
}

# Flat ordered list of topics (category order preserved)
ORDERED_TOPICS: List[str] = [
    t for topics in TOPIC_CATEGORIES.values() for t in topics
]

# ---------- SEARCH QUERIES ----------
# Each topic maps to the single most effective search query.
# We prefer GitHub topic: qualifier first, then fall back to keyword search.

TOPIC_QUERIES: Dict[str, str] = {
    # Foundations & Core ML
    "machine-learning":       "machine learning tutorial guide",
    "deep-learning":          "deep learning tutorial guide",
    "neural-networks":        "neural networks tutorial guide",
    "supervised-learning":    "supervised learning classification tutorial",
    "unsupervised-learning":  "unsupervised learning clustering tutorial",
    "reinforcement-learning": "reinforcement learning tutorial guide",
    "transfer-learning":      "transfer learning fine tuning tutorial",
    "optimization-algorithms":"gradient descent optimization tutorial",
    "feature-engineering":    "feature engineering tutorial guide",
    "model-evaluation":       "model evaluation metrics tutorial",

    # Frameworks & Libraries
    "pytorch":                "pytorch tutorial learn",
    "tensorflow":             "tensorflow tutorial learn",
    "keras":                  "keras tutorial learn",
    "scikit-learn":           "scikit learn tutorial guide",
    "xgboost":                "xgboost tutorial guide",
    "lightgbm":               "lightgbm tutorial guide",
    "catboost":               "catboost tutorial guide",
    "huggingface-transformers":"huggingface transformers tutorial guide",
    "langchain":              "langchain tutorial guide",
    "fastai":                 "fastai tutorial guide",

    # NLP
    "nlp":                    "natural language processing tutorial guide",
    "text-classification":    "text classification tutorial",
    "sentiment-analysis":     "sentiment analysis tutorial",
    "named-entity-recognition":"named entity recognition ner tutorial",
    "question-answering":     "question answering model tutorial",
    "translation-models":     "neural machine translation tutorial",
    "summarization":          "text summarization tutorial",
    "chatbots":               "chatbot ai tutorial build",

    # Generative AI & LLMs
    "generative-ai":          "generative ai tutorial guide",
    "llms":                   "large language model llm tutorial",
    "transformers":           "transformer architecture tutorial guide",
    "attention-mechanisms":   "attention mechanism tutorial",
    "vision-transformers":    "vision transformer vit tutorial",

    # Computer Vision
    "computer-vision":        "computer vision tutorial guide",
    "image-classification":   "image classification cnn tutorial",
    "object-detection":       "object detection tutorial yolo",
    "image-segmentation":     "image segmentation tutorial",
    "image-processing":       "image processing opencv tutorial",
    "face-recognition":       "face recognition tutorial",
    "ocr":                    "optical character recognition ocr tutorial",
    "pose-estimation":        "pose estimation tutorial",
    "gesture-recognition":    "gesture recognition tutorial",
    "video-analytics":        "video analytics ai tutorial",

    # Data Science & Analysis
    "data-science":           "data science tutorial guide learn",
    "exploratory-data-analysis":"exploratory data analysis eda tutorial",
    "statistics":             "statistics probability tutorial",
    "data-cleaning":          "data cleaning preprocessing tutorial",
    "pandas":                 "pandas tutorial guide",
    "numpy":                  "numpy tutorial guide",
    "data-visualization":     "data visualization tutorial guide",
    "matplotlib":             "matplotlib tutorial guide",
    "seaborn":                "seaborn visualization tutorial",
    "plotly":                 "plotly interactive visualization tutorial",

    # MLOps & Deployment
    "mlops":                  "mlops tutorial guide",
    "model-deployment":       "model deployment tutorial production",
    "model-serving":          "model serving api tutorial",
    "docker-for-ml":          "docker machine learning tutorial",
    "kubernetes-ml":          "kubernetes ml deployment tutorial",
    "airflow":                "apache airflow tutorial guide",
    "ci-cd":                  "ci cd machine learning tutorial",
    "data-pipelines":         "data pipeline etl tutorial",

    # Data Engineering
    "data-engineering":       "data engineering tutorial guide",
    "apache-spark":           "apache spark pyspark tutorial",
    "big-data":               "big data hadoop spark tutorial",

    # Applied AI
    "time-series":            "time series forecasting tutorial",
    "forecasting":            "forecasting predictive modeling tutorial",
    "recommendation-systems": "recommendation system tutorial",
    "anomaly-detection":      "anomaly detection tutorial",
    "ai-in-healthcare":       "ai healthcare machine learning tutorial",
    "ai-in-finance":          "ai finance fintech tutorial",
    "ai-in-education":        "ai education edtech tutorial",
    "ai-in-manufacturing":    "ai manufacturing industry tutorial",
    "ai-in-agriculture":      "ai agriculture farming tutorial",
    "ai-in-marketing":        "ai marketing analytics tutorial",

    # Advanced Research
    "graph-neural-networks":  "graph neural network gnn tutorial",
    "explainable-ai":         "explainable ai xai tutorial",
    "self-supervised-learning":"self supervised learning tutorial",
    "semi-supervised-learning":"semi supervised learning tutorial",
    "meta-learning":          "meta learning tutorial",
    "bayesian-learning":      "bayesian inference learning tutorial",
    "causal-inference":       "causal inference tutorial",

    # Robotics & Edge AI
    "robotics-ai":            "robotics ai tutorial guide",
    "autonomous-systems":     "autonomous systems tutorial",
    "edge-ai":                "edge ai tinyml tutorial",
    "iot-ai":                 "iot ai embedded tutorial",
    "path-planning":          "path planning robot tutorial",
    "sensor-fusion":          "sensor fusion tutorial",
    "drone-ai":               "drone computer vision tutorial",
    "reinforcement-robots":   "robot reinforcement learning tutorial",
    "control-systems":        "control systems ai tutorial",
    "sim2real":               "sim to real robotics tutorial",

    # Developer Tools & Fundamentals
    "python":                 "python tutorial learn programming",
    "sql":                    "sql tutorial learn data",
    "r":                      "r programming tutorial data science",
    "git":                    "git version control tutorial",
    "docker":                 "docker container tutorial guide",
    "api-development":        "fastapi rest api tutorial",
    "cloud-computing":        "aws gcp azure cloud tutorial",
    "bash-scripting":         "bash linux scripting tutorial",
    "testing-ml":             "machine learning testing tutorial",
}


# ---------- REPO TYPE CLASSIFICATION ----------
TYPE_SIGNALS: Dict[str, List[str]] = {
    "awesome-list":  ["awesome"],
    "dataset":       ["dataset", "datasets", "corpus", "benchmark", "data-set"],
    "research":      ["paper", "papers", "research", "arxiv", "survey", "thesis", "publication"],
    "tutorial":      ["tutorial", "tutorials", "guide", "guides", "learn", "course", "curriculum", "bootcamp", "education"],
    "playground":    ["playground", "notebook", "notebooks", "example", "examples", "demo", "demos", "colab", "exercises", "practice"],
    "tool":          ["tool", "tools", "library", "framework", "api", "sdk", "cli", "utility", "utilities", "platform"],
}

def classify_repo_type(name: str, description: str, topics: List[str]) -> str:
    combined = f"{name} {description} {' '.join(topics)}".lower()
    for repo_type, signals in TYPE_SIGNALS.items():
        if any(s in combined for s in signals):
            return repo_type
    return "project"


# ---------- RELEVANCE CHECK ----------
LEARNING_SIGNALS = {
    "tutorial", "guide", "learn", "learning", "course", "example",
    "examples", "notebook", "notebooks", "demo", "demos", "exercises",
    "awesome", "playground", "handbook", "cheatsheet", "resource",
    "resources", "reference", "study", "education", "curriculum",
    "bootcamp", "workshop", "lecture", "notes", "material",
}

def is_relevant(name: str, description: str, topics: List[str], query: str) -> bool:
    combined = f"{name} {description} {' '.join(topics)}".lower()

    # Check for learning signals
    if any(signal in combined for signal in LEARNING_SIGNALS):
        return True

    # Check if query words appear in combined text
    for word in query.lower().split():
        if len(word) > 3 and word in combined:
            return True

    return False


# ---------- HTTP HELPERS ----------
session = requests.Session()
session.headers.update(HEADERS)

def request_with_retry(url: str, params: dict = None, max_attempts: int = 4) -> Optional[requests.Response]:
    for attempt in range(max_attempts):
        try:
            r = session.get(url, params=params, timeout=20)
        except requests.RequestException as e:
            print(f"  Network error: {e}. Retrying...")
            time.sleep(3 * (attempt + 1))
            continue

        if r.status_code == 200:
            _check_rate_limit(r)
            return r

        if r.status_code in (403, 429):
            reset = r.headers.get("X-RateLimit-Reset")
            wait = max(int(reset) - int(time.time()), 5) if reset else 30 * (2 ** attempt)
            print(f"  Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue

        if r.status_code >= 500:
            time.sleep(4 * (attempt + 1))
            continue

        print(f"  Request failed [{r.status_code}]: {url}")
        return None

    return None


def _check_rate_limit(response: requests.Response) -> None:
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining and int(remaining) < 10:
        reset = response.headers.get("X-RateLimit-Reset")
        if reset:
            wait = max(int(reset) - int(time.time()), 1)
            print(f"  Rate limit low ({remaining} remaining). Waiting {wait}s...")
            time.sleep(wait)


# ---------- SEARCH ----------
def search_repos(query: str) -> List[dict]:
    params = {
        "q": f"{query} fork:false",
        "sort": "stars",
        "order": "desc",
        "per_page": PER_PAGE,
    }
    r = request_with_retry(GITHUB_API_SEARCH, params=params)
    if not r:
        return []
    data = r.json()
    return data.get("items", [])


def parse_repo(item: dict, topic: str) -> Optional[dict]:
    stars = item.get("stargazers_count", 0)
    if stars < MIN_STARS:
        return None

    name        = item.get("name") or ""
    full_name   = item.get("full_name") or ""
    description = item.get("description") or ""
    topics      = item.get("topics") or []
    language    = item.get("language") or ""
    pushed_at   = item.get("pushed_at") or ""
    license_obj = item.get("license") or {}
    license_id  = license_obj.get("spdx_id") or license_obj.get("name") or ""

    # Shorten date to YYYY-MM
    last_updated = pushed_at[:7] if pushed_at else ""

    repo_type = classify_repo_type(name, description, topics)

    return {
        "topic":        topic,
        "name":         name,
        "full_name":    full_name,
        "url":          item.get("html_url") or "",
        "stars":        stars,
        "description":  description[:140] if description else "",
        "owner":        (item.get("owner") or {}).get("login") or "",
        "language":     language,
        "last_updated": last_updated,
        "license":      license_id,
        "repo_type":    repo_type,
    }


# ---------- MAIN CRAWL ----------
def crawl_all() -> None:
    all_results: List[dict] = []
    seen_repos: Set[str] = set()   # Global dedup by full_name

    total_topics = len(ORDERED_TOPICS)

    for idx, topic in enumerate(ORDERED_TOPICS, 1):
        query = TOPIC_QUERIES.get(topic)
        if not query:
            continue

        print(f"[{idx:3}/{total_topics}] {topic}")

        items = search_repos(query)
        if not items:
            print(f"       No results.")
            time.sleep(1)
            continue

        candidates = []
        for item in items:
            full_name = item.get("full_name")
            if not full_name:
                continue

            # Global dedup: skip if another topic already claimed this repo
            if full_name in seen_repos:
                continue

            # Relevance check
            name        = item.get("name") or ""
            description = item.get("description") or ""
            topics      = item.get("topics") or []
            if not is_relevant(name, description, topics, query):
                continue

            repo = parse_repo(item, topic)
            if repo:
                candidates.append(repo)

        if not candidates:
            print(f"       No relevant repos found.")
            time.sleep(1)
            continue

        # Sort by stars, take top-K
        candidates.sort(key=lambda x: x["stars"], reverse=True)
        top = candidates[:TOP_K]

        for repo in top:
            seen_repos.add(repo["full_name"])
            all_results.append(repo)

        print(f"       {len(top)} repos collected (top: {top[0]['stars']} stars)")

        # Gentle pacing between topics
        time.sleep(1.5 + random.random())

    # Save results
    if not all_results:
        print("No repositories collected.")
        return

    cols = [
        "topic", "name", "full_name", "url", "stars",
        "description", "owner", "language",
        "last_updated", "license", "repo_type",
    ]
    df = pd.DataFrame(all_results)[cols]
    df.to_csv("repos.csv", index=False)
    print(f"\nSaved {len(df)} repositories across {df['topic'].nunique()} topics to repos.csv")


if __name__ == "__main__":
    crawl_all()
