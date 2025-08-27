# crawler.py
import os
import requests
import pandas as pd
import logging
from time import sleep
from typing import List, Dict, Any

# -------------------- CONFIG --------------------
GITHUB_API_URL = "https://api.github.com/search/repositories"
TOKEN = os.getenv("GITHUB_TOKEN")  # 🔑 Set in GitHub Actions or local env
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
OUTPUT_FILE = "learning_repos.csv"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# -------------------- TOPICS --------------------
TOPICS: Dict[str, str] = {
    # 1. Math & Foundations
    "math for ai": "linear algebra OR calculus OR probability OR optimization tutorial notebook",

    # 2. Programming
    "python for ai": "python machine learning tutorial OR course OR 30-days",
    "software engineering basics": "git docker pytest debugging machine learning",

    # 3. Data Handling
    "data engineering": "pandas data cleaning EDA tutorial notebook",
    "data pipelines": "spark dvc dataset versioning tutorial",

    # 4. Classic ML
    "machine learning basics": "scikit-learn tutorial examples beginner",
    "ensemble methods": "xgboost lightgbm tutorial notebook",

    # 5. Deep Learning
    "deep learning basics": "neural networks pytorch tensorflow tutorial",
    "transformers": "transformer attention tutorial huggingface notebook",

    # 6. NLP
    "nlp basics": "tokenization embeddings bert gpt huggingface tutorial",
    "rag & llms": "retrieval augmented generation langchain huggingface tutorial",

    # 7. Computer Vision
    "computer vision basics": "image classification object detection tutorial",
    "generative vision": "diffusion models stable diffusion style transfer repo",

    # 8. Reinforcement Learning
    "reinforcement learning": "reinforcement learning tutorial openai gym ppo dqn",

    # 9. Graph ML
    "graph neural networks": "graph neural network pytorch geometric dgl tutorial",

    # 10. Time Series & Speech
    "time series": "forecasting arima prophet tutorial notebook",
    "speech processing": "speech recognition tts asr tutorial repo",

    # 11. MLOps & Deployment
    "mlops basics": "mlops pipeline mlflow weights and biases tutorial",
    "model deployment": "fastapi flask streamlit model deployment example",

    # 12. Libraries & Ecosystem
    "hugging face": "huggingface transformers datasets accelerate tutorial",
    "langchain": "langchain chatbot rag tutorial examples",
    "fastai & pytorch lightning": "fastai pytorch lightning tutorial notebook",

    # 13. Domain Applications
    "recommender systems": "recommender system collaborative filtering tutorial",
    "healthcare ai": "medical imaging machine learning tutorial",
    "finance ai": "fraud detection stock prediction machine learning tutorial",

    # 14. Fun & Exploration
    "ai playground": "gradio streamlit demo interactive machine learning",
    "creative ai": "magenta music ai art generation tutorial",
    "ai image fun": "stable diffusion dalle mini image generation fun repo",
}

# -------------------- CORE FUNCTIONS --------------------
def fetch_repos(query: str, per_topic: int = 5, retries: int = 3) -> List[Dict[str, Any]]:
    """Fetch top repos from GitHub search for a given query with retry logic."""
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_topic}

    for attempt in range(retries):
        response = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)

        if response.status_code == 200:
            return response.json().get("items", [])

        logging.warning(
            f"⚠️ Error fetching {query} (status {response.status_code}). "
            f"Attempt {attempt+1}/{retries}."
        )
        sleep(2 * (attempt + 1))  # exponential backoff

    logging.error(f"❌ Failed to fetch results for query: {query}")
    return []


def crawl_topics(topics: Dict[str, str], per_topic: int = 5) -> pd.DataFrame:
    """Crawl repos for all topics and return as DataFrame."""
    results: List[Dict[str, Any]] = []

    for topic, query in topics.items():
        logging.info(f"🔍 Crawling topic: {topic}")
        repos = fetch_repos(query, per_topic)
        for repo in repos:
            results.append(
                {
                    "topic": topic,
                    "repo_name": repo["name"],
                    "owner": repo["owner"]["login"],
                    "url": repo["html_url"],
                    "stars": repo["stargazers_count"],
                }
            )

    df = pd.DataFrame(results).drop_duplicates(subset=["url"])
    return df


# -------------------- MAIN --------------------
if __name__ == "__main__":
    df = crawl_topics(TOPICS, per_topic=5)

    if df.empty:
        logging.warning("⚠️ No repositories found.")
    else:
        df.to_csv(OUTPUT_FILE, index=False)
        logging.info(f"✅ Done! Saved {len(df)} repos to {OUTPUT_FILE}")
        print(df.head(20))
