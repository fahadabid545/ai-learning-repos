# crawler.py
import requests
import pandas as pd
import time, random

GITHUB_API_URL = "https://api.github.com/search/repositories"
TOKEN = None  # 🔑 Add your GitHub token for higher rate limits
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

# 🎯 Topics → queries
TOPIC_QUERIES = {
    # Programming & Data Science
    "python": ["python tutorial", "learn python", "30 days python"],
    "pandas": ["pandas tutorial", "learn pandas"],
    "numpy": ["numpy tutorial", "learn numpy"],
    "r": ["learn r", "r tutorial", "data science with r"],

    # Core AI/ML
    "machine-learning": ["machine learning tutorial", "ml course", "learn machine learning"],
    "deep-learning": ["deep learning tutorial", "dl course", "learn deep learning"],
    "keras": ["keras tutorial", "learn keras"],

    # AI Domains
    "nlp": ["nlp tutorial", "learn nlp", "natural language processing course"],
    "computer-vision": ["computer vision tutorial", "cv course"],
    "generative-ai": ["generative ai tutorial", "learn generative ai"],
    "agentic-ai": ["agentic ai tutorial", "learn agentic ai"],
    "rag": ["rag tutorial", "retrieval augmented generation tutorial"],
    "langchain": ["langchain tutorial", "learn langchain"],

    # Latest Models & Tech
    "latest-models": [
        "gpt tutorial", "llama tutorial", "mistral tutorial",
        "phi tutorial", "deepseek tutorial", "gemini tutorial",
        "open source llm tutorial"
    ],

    # Playgrounds & Interactive
    "playgrounds": [
        "ml playground", "ai playground", "rag playground",
        "langchain playground", "notebooks tutorial"
    ]
}

# ⭐ Minimum stars per topic
MIN_STARS_BY_TOPIC = {
    "latest-models": 200,
    "generative-ai": 150,
    "agentic-ai": 150,
    "rag": 100,
    "langchain": 100,
    "playgrounds": 50,
    "default": 30,
}

# ✅ Keywords for filtering
LEARNING_KEYWORDS = ["tutorial", "course", "learn", "guide", "examples", "notebooks"]
PLAYGROUND_KEYWORDS = ["playground", "interactive", "notebook", "hands-on"]

def fetch_repos(query: str, per_page: int = 20):
    params = {
        "q": f"{query} in:name,description,readme fork:false",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
    }

    for attempt in range(3):  # retry up to 3 times
        r = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
        if r.status_code == 200:
            return r.json().get("items", [])
        elif r.status_code == 403:  # rate limited
            reset = r.headers.get("X-RateLimit-Reset")
            if reset:
                wait_time = max(int(reset) - int(time.time()), 1)
            else:
                wait_time = 30 * (2 ** attempt)  # exponential backoff
            print(f"⏳ Rate limit hit. Sleeping {wait_time}s...")
            time.sleep(wait_time)
        else:
            print(f"⚠️ Request failed [{r.status_code}]: {r.text}")
            time.sleep(5 * (attempt + 1))
    return []

def filter_repo(repo, topic):
    desc = (repo.get("description") or "").lower()
    name = repo.get("name", "").lower()

    if not any(kw in desc or kw in name for kw in LEARNING_KEYWORDS + PLAYGROUND_KEYWORDS):
        return False

    stars = repo.get("stargazers_count", 0)
    min_stars = MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_BY_TOPIC["default"])
    return stars >= min_stars

def crawl_all():
    all_repos = []
    seen_urls = set()

    for topic, queries in TOPIC_QUERIES.items():
        print(f"\n🔎 Crawling topic: {topic}")
        for q in queries:
            repos = fetch_repos(q)
            for repo in repos:
                if not filter_repo(repo, topic):
                    continue

                url = repo.get("html_url")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                all_repos.append({
                    "topic": topic,
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "url": url,
                    "stars": repo.get("stargazers_count", 0),
                    "description": repo.get("description"),
                })

            time.sleep(2 + random.random() * 3)  # gentle pacing

    # Sort & prioritize
    df = pd.DataFrame(all_repos)
    if not df.empty:
        df = df.sort_values(by="stars", ascending=False)
        df = df[["topic", "name", "full_name", "url", "stars", "description"]]
        df.to_csv("repos.csv", index=False)
        print(f"\n✅ Saved {len(df)} repos to repos.csv")
    else:
        print("⚠️ No repositories found.")

if __name__ == "__main__":
    crawl_all()
