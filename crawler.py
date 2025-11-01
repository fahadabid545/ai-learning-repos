"""
Improved GitHub crawler for learning resources.

Features:
- ~50 sensible topics
- stronger relevance filtering using repo details + README content
- tries to extract owner email (owner profile first, then README)
- returns top 5 starred repos per topic
- gentle pacing + basic retry/backoff
- minimal & focused
"""
import base64
import json
import re
import time
import random
from typing import List, Dict, Optional

import requests
import pandas as pd

# ---------- CONFIG ----------
GITHUB_API_SEARCH = "https://api.github.com/search/repositories"
GITHUB_API_REPO = "https://api.github.com/repos/{full_name}"
GITHUB_API_USER = "https://api.github.com/users/{login}"
GITHUB_API_README = "https://api.github.com/repos/{full_name}/readme"

TOKEN = None  # Optional: set your GitHub token string here for higher rate limits
HEADERS = {
    "Accept": "application/vnd.github+json, application/vnd.github.mercy-preview+json"
}
if TOKEN:
    HEADERS["Authorization"] = f"token {TOKEN}"

# tune limits
PER_PAGE = 50
MAX_PER_TOPIC_CANDIDATES = 40  # collect candidates, then pick top 5
TOP_K = 5

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# ---------- TOPICS (50+) ----------
TOPIC_QUERIES = {
    # 🧠 Core Machine Learning
    "machine-learning": ["machine learning tutorial", "learn machine learning"],
    "deep-learning": ["deep learning tutorial", "learn deep learning"],
    "reinforcement-learning": ["reinforcement learning tutorial", "rl tutorial"],
    "supervised-learning": ["supervised learning tutorial", "classification tutorial"],
    "unsupervised-learning": ["unsupervised learning tutorial", "clustering tutorial"],
    "transfer-learning": ["transfer learning tutorial", "fine tuning tutorial"],
    "neural-networks": ["neural networks tutorial", "build neural network"],
    "optimization-algorithms": ["gradient descent tutorial", "optimization tutorial"],
    "feature-engineering": ["feature engineering tutorial", "feature selection tutorial"],
    "model-evaluation": ["model evaluation tutorial", "metrics tutorial"],

    # 🧩 Frameworks & Libraries
    "pytorch": ["pytorch tutorial", "learn pytorch"],
    "tensorflow": ["tensorflow tutorial", "learn tensorflow"],
    "keras": ["keras tutorial", "learn keras"],
    "scikit-learn": ["scikit learn tutorial", "learn scikit-learn"],
    "xgboost": ["xgboost tutorial", "learn xgboost"],
    "lightgbm": ["lightgbm tutorial", "learn lightgbm"],
    "catboost": ["catboost tutorial", "learn catboost"],
    "huggingface-transformers": ["transformers tutorial", "huggingface tutorial"],
    "langchain": ["langchain tutorial", "learn langchain"],
    "fastai": ["fastai tutorial", "learn fastai"],

    # 🧬 Data Science & Analysis
    "data-science": ["data science tutorial", "learn data science"],
    "pandas": ["pandas tutorial", "learn pandas"],
    "numpy": ["numpy tutorial", "learn numpy"],
    "data-visualization": ["data visualization tutorial", "learn matplotlib"],
    "matplotlib": ["matplotlib tutorial", "plotting tutorial"],
    "seaborn": ["seaborn tutorial", "data visualization seaborn"],
    "plotly": ["plotly tutorial", "interactive plots tutorial"],
    "statistics": ["statistics tutorial", "probability tutorial"],
    "data-cleaning": ["data cleaning tutorial", "data preprocessing tutorial"],
    "exploratory-data-analysis": ["eda tutorial", "exploratory data analysis tutorial"],

    # 💬 Natural Language Processing
    "nlp": ["nlp tutorial", "natural language processing tutorial"],
    "text-classification": ["text classification tutorial", "text categorization tutorial"],
    "sentiment-analysis": ["sentiment analysis tutorial", "emotion detection tutorial"],
    "named-entity-recognition": ["ner tutorial", "named entity recognition tutorial"],
    "question-answering": ["qa model tutorial", "question answering tutorial"],
    "translation-models": ["translation tutorial", "seq2seq translation tutorial"],
    "summarization": ["text summarization tutorial", "abstractive summarization tutorial"],
    "generative-ai": ["generative ai tutorial", "learn generative ai"],
    "llms": ["large language model tutorial", "llm tutorial"],
    "chatbots": ["chatbot tutorial", "rasa tutorial", "ai chatbot course"],

    # 👁️ Computer Vision
    "computer-vision": ["computer vision tutorial", "learn computer vision"],
    "image-processing": ["image processing tutorial", "opencv tutorial"],
    "object-detection": ["object detection tutorial", "yolo tutorial"],
    "face-recognition": ["face recognition tutorial", "facial recognition ai"],
    "image-segmentation": ["image segmentation tutorial", "mask rcnn tutorial"],
    "video-analytics": ["video analytics tutorial", "video ai tutorial"],
    "image-classification": ["image classification tutorial", "cnn tutorial"],
    "gesture-recognition": ["gesture recognition tutorial", "hand tracking ai"],
    "pose-estimation": ["pose estimation tutorial", "openpose tutorial"],
    "ocr": ["ocr tutorial", "text detection ai"],

    # 🧮 Data Engineering / MLOps
    "data-engineering": ["data engineering tutorial", "learn data engineering"],
    "data-pipelines": ["data pipeline tutorial", "etl pipeline tutorial"],
    "big-data": ["big data tutorial", "spark tutorial"],
    "apache-spark": ["apache spark tutorial", "pyspark tutorial"],
    "airflow": ["airflow tutorial", "data workflow tutorial"],
    "mlops": ["mlops tutorial", "machine learning ops tutorial"],
    "model-serving": ["model serving tutorial", "api model deployment"],
    "docker-for-ml": ["docker tutorial", "dockerize ml model"],
    "kubernetes-ml": ["kubernetes tutorial", "ml kubernetes tutorial"],
    "model-deployment": ["model deployment tutorial", "deploy model tutorial"],

    # 🌐 Specialized / Applied AI
    "recommendation-systems": ["recommender tutorial", "recommendation system tutorial"],
    "anomaly-detection": ["anomaly detection tutorial", "outlier detection tutorial"],
    "time-series": ["time series tutorial", "forecasting tutorial"],
    "forecasting": ["forecasting tutorial", "predictive modeling tutorial"],
    "ai-in-healthcare": ["ai healthcare tutorial", "healthcare ml tutorial"],
    "ai-in-finance": ["ai finance tutorial", "fintech ai tutorial"],
    "ai-in-education": ["ai education tutorial", "education ai tutorial"],
    "ai-in-manufacturing": ["ai manufacturing tutorial", "industry 4.0 ai"],
    "ai-in-agriculture": ["ai agriculture tutorial", "farming ai tutorial"],
    "ai-in-marketing": ["ai marketing tutorial", "marketing analytics ai"],

    # 🧠 Advanced / Research Areas
    "explainable-ai": ["explainable ai tutorial", "xai tutorial"],
    "causal-inference": ["causal inference tutorial", "causality tutorial"],
    "bayesian-learning": ["bayesian learning tutorial", "bayesian inference tutorial"],
    "self-supervised-learning": ["self supervised learning tutorial", "representation learning tutorial"],
    "semi-supervised-learning": ["semi supervised learning tutorial", "weak supervision tutorial"],
    "meta-learning": ["meta learning tutorial", "learning to learn tutorial"],
    "graph-neural-networks": ["gnn tutorial", "graph neural network tutorial"],
    "attention-mechanisms": ["attention mechanism tutorial", "transformer attention tutorial"],
    "transformers": ["transformer tutorial", "attention is all you need tutorial"],
    "vision-transformers": ["vision transformer tutorial", "vit tutorial"],

    # 🤖 Robotics / Edge / Autonomous
    "robotics-ai": ["robotics tutorial", "ai robotics tutorial"],
    "autonomous-systems": ["autonomous systems tutorial", "autonomous vehicles tutorial"],
    "drone-ai": ["drone ai tutorial", "drone computer vision tutorial"],
    "edge-ai": ["edge ai tutorial", "tinyml tutorial"],
    "iot-ai": ["iot ai tutorial", "embedded ai tutorial"],
    "reinforcement-robots": ["robot reinforcement learning tutorial", "robot control ai"],
    "path-planning": ["path planning tutorial", "robot navigation tutorial"],
    "control-systems": ["control systems ai", "pid control tutorial"],
    "sensor-fusion": ["sensor fusion tutorial", "lidar radar ai"],
    "sim2real": ["sim2real tutorial", "robotics transfer learning"],

    # ⚙️ Developer Productivity / Fundamentals
    "python": ["python tutorial", "learn python"],
    "r": ["r tutorial", "learn r"],
    "sql": ["sql tutorial", "learn sql for data"],
    "git": ["git tutorial", "version control tutorial"],
    "api-development": ["api tutorial", "fastapi tutorial"],
    "testing-ml": ["ml testing tutorial", "unit testing ml"],
    "ci-cd": ["ci cd tutorial", "github actions tutorial"],
    "docker": ["docker tutorial", "container tutorial"],
    "bash-scripting": ["bash tutorial", "linux scripting tutorial"],
    "cloud-computing": ["cloud tutorial", "aws gcp azure tutorial"],
}

# keywords used to quickly identify learning resources
LEARNING_KEYWORDS = {"tutorial", "guide", "learn", "examples", "notebook", "course", "hands-on", "examples"}

session = requests.Session()
session.headers.update(HEADERS)


# ---------- helpers ----------
def request_with_retry(url: str, params: dict = None, max_attempts: int = 3) -> Optional[requests.Response]:
    for attempt in range(max_attempts):
        r = session.get(url, params=params, timeout=20)
        if r.status_code == 200:
            return r
        if r.status_code == 403:  # rate-limited
            reset = r.headers.get("X-RateLimit-Reset")
            if reset:
                wait = max(int(reset) - int(time.time()), 1)
            else:
                wait = 5 * (2 ** attempt)
            print(f"⏳ Rate limit or blocked. Sleeping {wait}s...")
            time.sleep(wait)
            continue
        # transient errors: small backoff
        if r.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        # other errors: break
        print(f"⚠️ Request failed [{r.status_code}] {url} - {r.text[:200]}")
        return None
    return None


def fetch_repos(query: str, per_page: int = PER_PAGE) -> List[dict]:
    params = {"q": f"{query} in:name,description,readme fork:false", "sort": "stars", "order": "desc", "per_page": per_page}
    r = request_with_retry(GITHUB_API_SEARCH, params=params)
    if not r:
        return []
    data = r.json()
    return data.get("items", [])


def get_repo_details(full_name: str) -> Optional[dict]:
    url = GITHUB_API_REPO.format(full_name=full_name)
    r = request_with_retry(url)
    if not r:
        return None
    return r.json()


def get_readme_text(full_name: str) -> Optional[str]:
    url = GITHUB_API_README.format(full_name=full_name)
    r = request_with_retry(url)
    if not r:
        return None
    try:
        data = r.json()
        content = data.get("content")
        encoding = data.get("encoding", "base64")
        if content and encoding == "base64":
            raw = base64.b64decode(content).decode(errors="ignore")
            return raw
        return None
    except Exception:
        return None


def extract_email(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None


def get_owner_email(owner_login: str) -> Optional[str]:
    url = GITHUB_API_USER.format(login=owner_login)
    r = request_with_retry(url)
    if not r:
        return None
    u = r.json()
    # public email sometimes present
    email = u.get("email")
    if email:
        return email
    # try blog/contact fields (sometimes contain emails)
    for field in ("bio", "blog", "company", "name"):
        txt = u.get(field) or ""
        e = extract_email(txt)
        if e:
            return e
    return None


def is_relevant(repo: dict, topic: str, queries: List[str], readme_text: Optional[str], details: Optional[dict]) -> bool:
    """Stricter relevance rules: keywords in name/desc/readme or topics match."""
    name = (repo.get("name") or "").lower()
    desc = (repo.get("description") or "").lower()
    readme = (readme_text or "").lower()
    # quick keyword check: any learning keyword in name/desc/readme
    if any(kw in name or kw in desc or kw in readme for kw in LEARNING_KEYWORDS):
        return True

    # check repo topics (if available)
    topics = details.get("topics", []) if details else []
    if topic.lower() in [t.lower() for t in topics]:
        return True

    # check if any query tokens show up in readme/desc/name
    for q in queries:
        qlower = q.lower()
        if qlower in name or qlower in desc or qlower in readme:
            return True

    return False


# ---------- main crawl ----------
def crawl_all():
    all_results = []
    for topic, queries in TOPIC_QUERIES.items():
        print(f"\n🔎 Crawling topic: {topic}")
        candidates = []
        seen = set()

        # build combined queries list (topic + configured queries)
        q_list = [topic] + queries

        for q in q_list:
            repos = fetch_repos(q)
            if not repos:
                continue
            for repo in repos:
                full_name = repo.get("full_name")
                if not full_name or full_name in seen:
                    continue
                seen.add(full_name)

                # quick pass: must have minimum star threshold to be considered
                stars = repo.get("stargazers_count", 0)
                if stars < 10:  # small floor; reduce noise
                    continue

                # fetch details and README for stronger relevance checks (costly but filtered)
                details = get_repo_details(full_name)
                time.sleep(0.5 + random.random() * 0.6)
                readme = get_readme_text(full_name)
                time.sleep(0.5 + random.random() * 0.6)

                if not is_relevant(repo, topic, queries, readme, details):
                    continue

                # Try to locate an email: owner profile first, then README
                owner = repo.get("owner", {}) or {}
                owner_login = owner.get("login")
                email = None
                if owner_login:
                    email = get_owner_email(owner_login)
                    time.sleep(0.4 + random.random() * 0.6)
                if not email:
                    email = extract_email(readme)

                candidates.append({
                    "topic": topic,
                    "name": repo.get("name"),
                    "full_name": full_name,
                    "url": repo.get("html_url"),
                    "stars": stars,
                    "description": repo.get("description"),
                    "owner": owner_login,
                    "owner_email": email,
                })

                # gentle pacing
                if len(candidates) >= MAX_PER_TOPIC_CANDIDATES:
                    break
            # small pause between different queries
            time.sleep(1 + random.random() * 1.5)
            if len(candidates) >= MAX_PER_TOPIC_CANDIDATES:
                break

        if not candidates:
            print(f"⚠️ No candidates found for {topic}")
            continue

        # pick top-K by stars per topic
        candidates_sorted = sorted(candidates, key=lambda x: x["stars"], reverse=True)[:TOP_K]
        for c in candidates_sorted:
            all_results.append(c)
        print(f"✅ Collected {len(candidates_sorted)} repos for {topic}")

    # save results
    if all_results:
        df = pd.DataFrame(all_results)
        cols = ["topic", "name", "full_name", "url", "stars", "description", "owner", "owner_email"]
        df = df[cols]
        df.to_csv("repos.csv", index=False)
        print(f"\n✅ Saved {len(df)} repos to repos.csv")
    else:
        print("⚠️ No repositories collected.")


if __name__ == "__main__":
    crawl_all()
