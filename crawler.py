import os
import requests
import pandas as pd
import time
import random
from typing import Optional

GITHUB_API_URL = "https://api.github.com/search/repositories"
TOKEN = os.getenv("GITHUB_TOKEN")  # set this in env for higher rate limits
# Use Accept header for topics preview if you want topics (not required)
HEADERS = {
    "Authorization": f"token {TOKEN}"
} if TOKEN else {}

# Topics and queries (unchanged from your original, shorten for clarity)
TOPIC_QUERIES = {

    "MCP": ["MCP tutorial", "learn MCP", "MCP and AI"],
    "Expert Systems": ["Expert systems", "AI Expert system"],
    "Robotic Process Automation (RPA)": ["Robotic Process Automation tutorial", "Robotic Process Automation Course"],
    "Reactive Machines": ["learn Reactive Machines", "Reactive Machines tutorial", "Ai with Reactive Machines"],

    "Edge AI": ["Edge Ai tutorial", "learn Edge AI", "Edge AI vs AI"],
    "Quantum AI": ["Quantum AI", "Quantum AI system"],
    "BLockChain with AI": ["AI in Blockchain tutorial", "Blockchain in AI Course"],
    "Augmented Reality With AI": ["learn Augmented Reality with AI", "AI Augmented Reality tutorial", "Ai with Augmented Reality"],
    
    "python": ["python tutorial", "learn python", "30 days python"],
    "pandas": ["pandas tutorial", "learn pandas"],
    "numpy": ["numpy tutorial", "learn numpy"],
    "r": ["learn r", "r tutorial", "data science with r"],

    "machine-learning": ["machine learning tutorial", "ml course", "learn machine learning"],
    "deep-learning": ["deep learning tutorial", "dl course", "learn deep learning"],
    "keras": ["keras tutorial", "learn keras"],
    "PyTorch": ["PyTorch tutorial", "learn PyTorch"],
    "TensorFlow": ["TensorFlow tutorial", "learn TensorFlow"], 
    "ScikitLearn": ["ScikitLearn tutorial", "learn ScikitLearn"],  

    "nlp": ["nlp tutorial", "learn nlp", "natural language processing course"],
    "computer-vision": ["computer vision tutorial", "cv course"],
    "generative-ai": ["generative ai tutorial", "learn generative ai"],
    "agentic-ai": ["agentic ai tutorial", "learn agentic ai"],
    "rag": ["rag tutorial", "retrieval augmented generation tutorial"],
    "langchain": ["langchain tutorial", "learn langchain"],

    "ai-education": ["ai in education", "education ai tutorial"],
    "ai-finance": ["ai in finance", "finance ai tutorial"],
    "ai-manufacturing": ["ai in manufacturing", "manufacturing ai tutorial"],
    "ai-healthcare": ["ai in healthcare", "healthcare ai tutorial"],
    "recommendation-systems": ["recommendation systems tutorial", "build recommender system"],
    "chatbots": ["chatbot tutorial", "learn chatbots", "ai chatbot course"],
    "ai-security": ["ai in security", "cybersecurity ai tutorial"],
    "object-detection": ["object detection tutorial", "learn object detection"],
    "ai-video-surveillance": ["ai video surveillance tutorial", "video analytics ai"],
    "ai-gaming": ["ai in gaming", "game ai tutorial"],
    "ai-ethics": ["ai ethics tutorial", "responsible ai"],
    "face-recognition": ["face recognition tutorial", "facial recognition ai"],
    "reinforcement-learning": ["reinforcement learning tutorial", "rl course"],
    "virtual-assistants": ["ai virtual assistants", "voice assistants ai"],

    "latest-models": [
        "gpt tutorial", "llama tutorial", "mistral tutorial",
        "phi tutorial", "deepseek tutorial", "gemini tutorial",
        "open source llm tutorial"
    ],

    "playgrounds": [
        "ml playground", "ai playground", "rag playground",
        "langchain playground", "notebooks tutorial"
    ]
}

# Tunable thresholds
MIN_STARS_BY_TOPIC = {
    "latest-models": 200,
    "generative-ai": 150,
    "agentic-ai": 150,
    "rag": 100,
    "langchain": 100,
    "playgrounds": 20,
    "default": 10,
}

LEARNING_KEYWORDS = ["tutorial", "course", "learn", "guide", "examples", "notebooks"]
PLAYGROUND_KEYWORDS = ["playground", "interactive", "notebook", "hands-on"]

# Controls
PER_PAGE = 100  # allowed max is usually 100
MAX_PER_TOPIC = 5
FETCH_README = True  # set to False to avoid extra API calls (fewer requests, less accurate)
REQUEST_PAUSE = 1.0  # base pause between requests

session = requests.Session()
if HEADERS:
    session.headers.update(HEADERS)
session.headers.update({"Accept": "application/vnd.github.v3+json"})

def fetch_repos(query: str, per_page: int = PER_PAGE, page: int = 1):
    # Quote queries that contain spaces to treat as phrase-search
    q = query if '"' in query else f'"{query}"'
    params = {
        "q": f"{q} in:name,description,readme fork:false",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }

    for attempt in range(3):
        r = session.get(GITHUB_API_URL, params=params)
        if r.status_code == 200:
            return r.json().get("items", [])
        elif r.status_code == 403:
            reset = r.headers.get("X-RateLimit-Reset")
            if reset:
                wait_time = max(int(reset) - int(time.time()), 1)
            else:
                wait_time = 30 * (2 ** attempt)
            print(f"⏳ Rate limit hit. Sleeping {wait_time}s...")
            time.sleep(wait_time)
        else:
            print(f"⚠️ Request failed [{r.status_code}]: {r.text}")
            time.sleep(5 * (attempt + 1))
    return []

def fetch_readme_full(owner_full_name: str) -> Optional[str]:
    """
    Fetch raw README text for a repo (owner/repo). Returns text or None.
    """
    url = f"https://api.github.com/repos/{owner_full_name}/readme"
    headers = {"Accept": "application/vnd.github.v3.raw"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.text.lower()
    except Exception as e:
        print("📛 README fetch error:", e)
    return None

def keyword_in_text_any(keywords, *texts):
    for kw in keywords:
        for t in texts:
            if not t:
                continue
            if kw in t:
                return True
    return False

def compute_relevance(repo, topic, readme_text: Optional[str]):
    """
    Returns True if repo looks relevant, based on:
     - keywords in name/description/readme
     - star threshold fallback
     - allow slight relaxations
    """
    name = (repo.get("name") or "").lower()
    desc = (repo.get("description") or "").lower()
    full_name = (repo.get("full_name") or "").lower()
    stars = repo.get("stargazers_count", 0)
    min_stars = MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_BY_TOPIC["default"])

    # First: look for learning/playground keywords in name/description/readme
    if keyword_in_text_any(LEARNING_KEYWORDS + PLAYGROUND_KEYWORDS, name, desc, full_name, readme_text or ""):
        # Accept if stars >= half of min_stars to permit smaller helpful repos
        if stars >= (min_stars // 2):
            return True

    # Second: if repo explicitly mentions the main topic token in name/full_name/desc/readme
    if topic.lower() in name or topic.lower() in full_name or topic.lower() in desc or (readme_text and topic.lower() in readme_text):
        return stars >= (min_stars // 2)

    # Final: fall back to star threshold (strict)
    return stars >= min_stars

def crawl_all():
    all_repos = []

    for topic, queries in TOPIC_QUERIES.items():
        print(f"\n🔎 Crawling topic: {topic}")
        seen_urls = set()
        topic_repos = []

        for q in queries:
            # fetch multiple pages until enough repos collected or pages exhausted (safe small loop)
            page = 1
            while len(topic_repos) < MAX_PER_TOPIC and page <= 3:  # up to 3 pages per query
                repos = fetch_repos(q, per_page=PER_PAGE, page=page)
                if not repos:
                    break

                for repo in repos:
                    if len(topic_repos) >= MAX_PER_TOPIC:
                        break

                    url = repo.get("html_url")
                    if url in seen_urls:
                        continue

                    readme_text = None
                    if FETCH_README:
                        # gentle random sleep between extra API calls
                        time.sleep(0.5 + random.random()*0.5)
                        readme_text = fetch_readme_full(repo.get("full_name"))

                    if compute_relevance(repo, topic, readme_text):
                        seen_urls.add(url)
                        topic_repos.append({
                            "topic": topic,
                            "name": repo.get("name"),
                            "full_name": repo.get("full_name"),
                            "url": url,
                            "stars": repo.get("stargazers_count", 0),
                            "description": repo.get("description"),
                        })

                page += 1
                time.sleep(REQUEST_PAUSE + random.random() * 1.5)

        if len(topic_repos) < MAX_PER_TOPIC:
            print(f"⚠️ Only found {len(topic_repos)} repos for {topic}")

        all_repos.extend(topic_repos)

    # Sort & save
    df = pd.DataFrame(all_repos)
    if not df.empty:
        df = df.sort_values(by=["topic", "stars"], ascending=[True, False])
        df = df[["topic", "name", "full_name", "url", "stars", "description"]]
        df.to_csv("repos.csv", index=False)
        print(f"\n✅ Saved {len(df)} repos to repos.csv")
    else:
        print("⚠️ No repositories found.")

if __name__ == "__main__":
    crawl_all()

