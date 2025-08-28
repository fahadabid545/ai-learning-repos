# crawler.py
import os
import time
import requests
import pandas as pd

GITHUB_API_URL = "https://api.github.com/search/repositories"
TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

# =========================
# Topics → learning-focused queries
# =========================
# =========================
# Topics → learning-focused queries
# =========================
TOPIC_QUERIES = {
    # Foundations
    "python": ["learn python in:name,description,readme", "python tutorial in:name,description,readme", "30 days python"],
    "r": ["learn R", "R programming tutorial", "R for data science"],
    "numpy": ["numpy tutorial", "learn numpy"],
    "pandas": ["pandas tutorial", "learn pandas", "pandas exercises"],
    "matplotlib-seaborn": ["matplotlib tutorial", "seaborn tutorial", "data viz tutorial"],

    # Core ML / DL
    "machine-learning": ["machine learning tutorial", "ml course", "ml from scratch"],
    "scikit-learn": ["scikit-learn tutorial", "learn scikit-learn", "sklearn examples"],
    "deep-learning": ["deep learning tutorial", "dl course", "neural networks from scratch"],
    "pytorch": ["pytorch tutorial", "learn pytorch", "pytorch beginner"],
    "tensorflow": ["tensorflow tutorial", "learn tensorflow", "tf beginner"],
    "keras": ["keras tutorial", "learn keras", "keras beginner"],

    # NLP / CV
    "nlp": ["nlp tutorial", "learn nlp", "nlp course"],
    "huggingface-transformers": ["transformers tutorial", "huggingface tutorial", "transformers examples"],
    "spacy": ["spacy tutorial", "learn spacy"],
    "computer-vision": ["computer vision tutorial", "cv course", "opencv tutorial"],
    "opencv": ["opencv tutorial", "learn opencv"],

    # GenAI / Agentic / RAG
    "generative-ai": ["generative ai tutorial", "genai course", "genai notebooks"],
    "agentic-ai": ["agentic ai tutorial", "agent workflows tutorial"],
    "rag": ["rag tutorial", "retrieval augmented generation tutorial", "build rag"],
    "langchain": ["langchain tutorial", "langchain cookbook", "langchain examples"],
    "llamaindex": ["llamaindex tutorial", "llamaindex examples"],
    "openai-api": ["openai api tutorial", "openai examples", "openai cookbook"],

    # MCP (Model Context Protocol) & tooling
    "mcp": ["model context protocol tutorial", "openai mcp tutorial", "mcp server template"],

    # Vector DBs / RAG infra
    "faiss": ["faiss tutorial", "faiss examples"],
    "chromadb": ["chromadb tutorial", "chroma tutorial"],
    "weaviate": ["weaviate tutorial"],
    "pinecone": ["pinecone tutorial"],

    # Prompting / LLMOps / MLOps
    "prompt-engineering": ["prompt engineering tutorial", "prompting cookbook"],
    "mlops": ["mlops tutorial", "mlops course", "mlflow tutorial"],
    "llmops": ["llmops tutorial", "production llm tutorial"],
    "mlflow": ["mlflow tutorial", "mlflow examples"],
    "wandb": ["weights and biases tutorial", "wandb tutorial"],

    # Extras often helpful for students
    "xgboost": ["xgboost tutorial"],
    "lightgbm": ["lightgbm tutorial"],
    "data-engineering-basics": ["etl tutorial", "data pipeline tutorial"],
    "sql-for-ml": ["sql tutorial beginners data", "learn sql data"],

    # 📌 Latest AI Models & Trends (no duplicate keys here)
    "transformers": ["transformers tutorial", "huggingface transformers course"],
    "llm": ["large language model tutorial", "learn llm"],
    "chatgpt": ["chatgpt tutorial", "openai chatgpt guide"],
    "diffusion-models": ["diffusion models tutorial", "stable diffusion guide"],
    "multimodal-ai": ["multimodal ai tutorial", "vision language models"],

    # Dedicated interactive/playground collections
    "projects": ["machine learning projects", "ai projects for beginners"],
    "playgrounds": ["ml playground", "ai playground", "rag playground", "langchain playground", "notebooks tutorial"]
}

# Learning & playground filters
LEARNING_KEYWORDS = [
    "learn", "tutorial", "course", "days", "guide", "book",
    "introduction", "from scratch", "roadmap", "curriculum",
    "exercises", "practice", "workshop", "hands-on", "cookbook",
    "examples", "notebooks", "labs", "bootcamp"
]

PLAYGROUND_KEYWORDS = [
    "playground", "notebook", "colab", "labs", "lab", "demo", "examples", "practice", "interactive"
]

# Per-topic minimum stars (fallback-friendly for niche tech)
MIN_STARS_DEFAULT = 100
MIN_STARS_BY_TOPIC = {
    "mcp": 10,
    "agentic-ai": 30,
    "rag": 30,
    "langchain": 30,
    "llamaindex": 20,
    "chromadb": 20,
    "faiss": 20,
    "weaviate": 20,
    "pinecone": 20,
    "playgrounds": 10,
    "openai-api": 30,
}

def min_stars_for(topic: str) -> int:
    return MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_DEFAULT)

def fetch_repos(query: str, per_page: int = 20):
    # Boost relevance with GitHub qualifiers
    # - Search in name/description/readme
    # - Exclude forks for cleaner learning material
    params = {
        "q": f"{query} in:name,description,readme fork:false",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page
    }
    r = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json().get("items", [])

def is_learning_repo(repo) -> bool:
    text = f"{repo.get('name','')} {repo.get('description','')}".lower()
    return any(k in text for k in LEARNING_KEYWORDS)

def is_playground_repo(repo) -> bool:
    text = f"{repo.get('name','')} {repo.get('description','')}".lower()
    return any(k in text for k in PLAYGROUND_KEYWORDS)

def unique_key(repo) -> str:
    return repo["html_url"]

def curate_for_topic(topic: str, queries: list[str], want: int = 5) -> list[dict]:
    preferred, normal = [], []
    seen = set()
    threshold = min_stars_for(topic)

    for q in queries:
        try:
            items = fetch_repos(q, per_page=30)
        except requests.HTTPError as e:
            print(f"HTTP error for query '{q}': {e}")
            continue

        for repo in items:
            # Popularity gating (topic-aware)
            if repo.get("stargazers_count", 0) < threshold:
                continue

            # Must be a learning resource
            if not is_learning_repo(repo):
                continue

            entry = {
                "topic": topic,
                "name": repo["name"],
                "owner": repo["owner"]["login"],
                "url": repo["html_url"],
                "stars": repo["stargazers_count"],
                "description": repo.get("description") or ""
            }
            key = unique_key(repo)
            if key in seen:
                continue
            seen.add(key)

            # Prefer interactive/playground resources
            if is_playground_repo(repo):
                preferred.append(entry)
            else:
                normal.append(entry)

            # Early exit if we already have enough (saves rate limit)
            if len(preferred) + len(normal) >= max(want * 2, 12):
                break

        # be polite to API
        time.sleep(0.6)

        # If we already have plenty, stop early
        if len(preferred) >= want or (len(preferred) + len(normal)) >= want * 2:
            break

    # Fill with playgrounds first, then regular
    curated = preferred[:want]
    if len(curated) < want:
        curated += normal[: (want - len(curated))]
    return curated

def main():
    all_rows = []
    for topic, queries in TOPIC_QUERIES.items():
        print(f"→ Collecting for topic: {topic}")
        curated = curate_for_topic(topic, queries, want=5)
        if not curated:
            print(f"⚠️ No repos found for topic '{topic}' at current threshold ({min_stars_for(topic)} stars)")
        all_rows.extend(curated)

    # Deduplicate globally by URL (in case same repo appears under multiple topics)
    dedup = {}
    for row in all_rows:
        dedup[row["url"]] = row
    rows = list(dedup.values())

    df = pd.DataFrame(rows, columns=["topic", "name", "owner", "url", "stars", "description"])
    df.sort_values(["topic", "stars"], ascending=[True, False], inplace=True)
    df.to_csv("repos.csv", index=False)
    print(f"✅ repos.csv generated with {len(df)} curated learning repos")

if __name__ == "__main__":
    main()
