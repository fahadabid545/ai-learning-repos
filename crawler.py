# crawler.py
import requests
import pandas as pd

GITHUB_API_URL = "https://api.github.com/search/repositories"
TOKEN = None  # 🔑 Add your GitHub token for higher rate limits
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

# 🎯 Refined topics → queries
TOPICS = {
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

def fetch_repos(query, per_topic=5):
    """Fetch top repos from GitHub search for a given query."""
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_topic
    }
    response = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
    if response.status_code != 200:
        print(f"⚠️ Error fetching {query}: {response.json()}")
        return []
    return response.json().get("items", [])

def crawl_topics(topics, per_topic=5):
    """Crawl repos for all topics and return as DataFrame."""
    results = []
    for topic, query in topics.items():
        repos = fetch_repos(query, per_topic)
        for repo in repos:
            results.append({
                "repo_name": repo["name"],                  # just repo name
                "owner": repo["owner"]["login"],            # owner username
                "url": repo["html_url"],                    # repo url
                "stars": repo["stargazers_count"]           # stargazers
            })
    return pd.DataFrame(results)

if __name__ == "__main__":
    df = crawl_topics(TOPICS, per_topic=5)
    df.to_csv("learning_repos.csv", index=False)
    print("✅ Done! Saved repos to learning_repos.csv")
    print(df.head(20))
