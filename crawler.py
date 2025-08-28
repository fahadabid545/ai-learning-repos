# crawler.py
import requests
import pandas as pd
import os

GITHUB_API_URL = "https://api.github.com/search/repositories"
TOKEN = os.getenv("GITHUB_TOKEN")  # use GitHub Actions secret
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

# 🎯 Topics → learning-focused queries
TOPIC_QUERIES = {
    "python": ["python tutorial", "learn python", "30 days python"],
    "pandas": ["pandas tutorial", "learn pandas"],
    "numpy": ["numpy tutorial", "learn numpy"],
    "machine-learning": ["machine learning tutorial", "ml course", "learn machine learning"],
    "deep-learning": ["deep learning tutorial", "dl course", "learn deep learning"],
    "nlp": ["nlp tutorial", "learn nlp", "natural language processing course"],
    "computer-vision": ["computer vision tutorial", "cv course"],
    "generative-ai": ["generative ai tutorial", "learn generative ai"],
    "agentic-ai": ["agentic ai tutorial", "learn agentic ai"],
    "artificial-intelligence": ["artificial intelligence tutorial", "learn ai", "ai for beginners"]
}

# ✅ learning-related keywords
LEARNING_KEYWORDS = ["learn", "tutorial", "course", "days", "guide", "book", "introduction"]


def fetch_repos(query, top_n=20):
    """Fetch repositories for a given search query"""
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": top_n
    }
    r = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json().get("items", [])


def is_learning_repo(repo):
    """Check if repo looks like a learning resource"""
    text = (repo.get("name", "") + " " + repo.get("description", "")).lower()
    return any(keyword in text for keyword in LEARNING_KEYWORDS)


def main():
    all_repos = []

    for topic, queries in TOPIC_QUERIES.items():
        collected = []
        for q in queries:
            repos = fetch_repos(q, top_n=20)
            for repo in repos:
                if (
                    repo["stargazers_count"] >= 100  # popularity filter
                    and is_learning_repo(repo)       # learning-focused
                ):
                    entry = {
                        "topic": topic,
                        "name": repo["name"],
                        "owner": repo["owner"]["login"],
                        "url": repo["html_url"],
                        "stars": repo["stargazers_count"],
                        "description": repo["description"] or ""
                    }
                    if entry not in collected:
                        collected.append(entry)

            if len(collected) >= 5:
                break  # stop once we have enough

        all_repos.extend(collected[:5])  # take top 5

    df = pd.DataFrame(all_repos)
    df.to_csv("repos.csv", index=False)
    print("✅ repos.csv generated with curated learning repos!")


if __name__ == "__main__":
    main()
