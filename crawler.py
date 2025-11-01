# crawler.py
"""
GitHub crawler for learning resources (AI / ML / DS).
- Topic-driven queries (30+ topics included)
- Candidate pool -> relevance scoring -> star-floor-first selection
- Email extraction attempts for later notifications
- Configurable controls and safe defaults
"""

import os
import time
import math
import random
import re
import requests
import pandas as pd
from typing import Optional, List, Dict
from difflib import SequenceMatcher

# ---------------------------
# Config / environment
# ---------------------------
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_API_URL = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")  # set this in env for higher rate limits
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
# Use topics preview header when fetching topics
TOPICS_ACCEPT_HEADER = {"Accept": "application/vnd.github.mercy-preview+json"}

# Topics and example queries (30+ topics). Edit or extend as needed.
TOPIC_QUERIES = {
    # --- Core Machine Learning & Deep Learning ---
    "machine-learning": ["machine learning tutorial", "learn machine learning", "ml course"],
    "deep-learning": ["deep learning tutorial", "learn deep learning", "dl projects"],
    "supervised-learning": ["supervised learning tutorial", "classification regression examples"],
    "unsupervised-learning": ["unsupervised learning tutorial", "clustering tutorial"],
    "reinforcement-learning": ["reinforcement learning tutorial", "rl projects", "learn reinforcement learning"],
    "transfer-learning": ["transfer learning tutorial", "fine tuning tutorial", "transfer learning examples"],
    "meta-learning": ["meta learning tutorial", "few shot learning tutorial"],

    # --- Libraries & Frameworks ---
    "pytorch": ["pytorch tutorial", "learn pytorch", "pytorch examples"],
    "tensorflow": ["tensorflow tutorial", "learn tensorflow", "tf projects"],
    "keras": ["keras tutorial", "learn keras", "keras examples"],
    "scikit-learn": ["scikit learn tutorial", "scikit-learn course", "learn scikit-learn"],
    "xgboost": ["xgboost tutorial", "gradient boosting tutorial"],
    "lightgbm": ["lightgbm tutorial", "learn lightgbm"],

    # --- Data Science Foundations ---
    "data-science": ["data science tutorial", "data science course", "learn data science"],
    "statistics-for-ai": ["statistics for ai tutorial", "probability and statistics tutorial"],
    "feature-engineering": ["feature engineering tutorial", "data preprocessing tutorial"],
    "data-visualization": ["data visualization tutorial", "matplotlib seaborn tutorial"],
    "python-for-data-science": ["python for data science tutorial", "python data projects"],
    "r-for-data-science": ["r for data science tutorial", "data analysis in r"],

    # --- Natural Language Processing (NLP) ---
    "natural-language-processing": ["nlp tutorial", "learn nlp", "nlp projects"],
    "transformers": ["transformers tutorial", "huggingface tutorial", "bert gpt tutorial"],
    "text-summarization": ["text summarization tutorial", "abstractive summarization tutorial"],
    "sentiment-analysis": ["sentiment analysis tutorial", "text classification tutorial"],
    "speech-recognition": ["speech recognition tutorial", "voice recognition ai tutorial"],

    # --- Computer Vision ---
    "computer-vision": ["computer vision tutorial", "learn computer vision", "cv projects"],
    "object-detection": ["object detection tutorial", "yolo tutorial", "detectron tutorial"],
    "image-segmentation": ["image segmentation tutorial", "semantic segmentation tutorial"],
    "face-recognition": ["face recognition tutorial", "facial recognition ai tutorial"],
    "image-generation": ["image generation tutorial", "diffusion models tutorial"],

    # --- Generative & Large Language Models ---
    "generative-ai": ["generative ai tutorial", "gpt tutorial", "diffusion models tutorial"],
    "large-language-models": ["llm tutorial", "gpt fine-tuning tutorial", "open source llm tutorial"],
    "langchain": ["langchain tutorial", "learn langchain", "langchain examples"],
    "retrieval-augmented-generation": ["rag tutorial", "retrieval augmented generation tutorial"],
    "prompt-engineering": ["prompt engineering tutorial", "llm prompting tutorial"],

    # --- MLOps & Deployment ---
    "mlops": ["mlops tutorial", "mlops pipeline tutorial", "deploy ml models"],
    "model-deployment": ["model deployment tutorial", "fastapi ml deployment", "docker ml tutorial"],
    "model-monitoring": ["model monitoring tutorial", "ml model drift tutorial"],
    "data-versioning": ["data versioning tutorial", "dvc tutorial"],

    # --- Applied AI Fields ---
    "ai-healthcare": ["ai in healthcare tutorial", "medical ai projects"],
    "ai-finance": ["ai in finance tutorial", "finance machine learning tutorial"],
    "ai-education": ["ai in education tutorial", "education ai tutorial"],
    "ai-manufacturing": ["ai in manufacturing tutorial", "industrial ai tutorial"],
    "ai-security": ["ai security tutorial", "cybersecurity ai tutorial"],
    "ai-ethics": ["ai ethics tutorial", "responsible ai tutorial", "explainable ai tutorial"],

    # --- Cutting-Edge & Emerging Areas ---
    "agentic-ai": ["agentic ai tutorial", "autonomous agents tutorial", "crew ai tutorial"],
    "multi-agent-systems": ["multi agent system tutorial", "ai agents collaboration tutorial"],
    "edge-ai": ["edge ai tutorial", "tensorflow lite tutorial", "ai on edge devices"],
    "quantum-ai": ["quantum ai tutorial", "quantum machine learning tutorial"],
    "blockchain-ai": ["blockchain and ai tutorial", "ai with blockchain tutorial"],
    "augmented-reality-ai": ["augmented reality ai tutorial", "ar with ai tutorial"],
    "ai-robotics": ["ai robotics tutorial", "robotic ai control tutorial"],

    # --- Specialized Applications ---
    "recommendation-systems": ["recommendation system tutorial", "recommender tutorial"],
    "chatbots": ["chatbot tutorial", "rasa tutorial", "dialogflow tutorial"],
    "virtual-assistants": ["virtual assistant tutorial", "voice assistant ai tutorial"],
    "ai-gaming": ["game ai tutorial", "ai in gaming tutorial"],
    "ai-music": ["ai music generation tutorial", "music ai tutorial"],
    "ai-video-surveillance": ["ai video surveillance tutorial", "video analytics ai tutorial"],

    # --- Tools, Demos & Playgrounds ---
    "playgrounds": ["ai playground", "ml playground", "interactive notebooks"],
    "notebooks-collections": ["awesome notebooks ai", "colab tutorial", "jupyter examples"],
}

# Per-topic minimum stars preference (adjust per your taste). Topics not listed use 'default'.
MIN_STARS_BY_TOPIC = {
    "generative-ai": 200,
    "transformers": 150,
    "langchain": 100,
    "retrieval-augmented-generation": 100,
    "pytorch": 100,
    "tensorflow": 100,
    "deep-learning": 150,
    "machine-learning": 150,
    "mlops": 100,
    "default": 30,
}

# Keyword hints (used implicitly by tokenizing topic & queries)
LEARNING_KEYWORDS = ["tutorial", "course", "learn", "guide", "examples", "notebooks", "examples"]
PLAYGROUND_KEYWORDS = ["playground", "interactive", "notebook", "hands-on", "demo"]

# ---------------------------
# Controls (tweak when experimenting)
# ---------------------------
PER_PAGE = 100                # GitHub allowed max per page
MAX_PER_TOPIC = 5             # how many final repos per topic you want
CANDIDATE_POOL_LIMIT = 300    # how many candidates to collect before scoring
MAX_PAGES_PER_QUERY = 3       # pages per query to fetch
FETCH_README = True           # expensive but improves relevance
FETCH_TOPICS = True           # fetch repo topics (needs token)
REQUEST_PAUSE = 1.0           # base pause between requests
DRY_RUN = True                # set False only when you're ready to write / notify

# ---------------------------
# Helpers & session
# ---------------------------
session = requests.Session()
if HEADERS:
    session.headers.update(HEADERS)
session.headers.update({"Accept": "application/vnd.github.v3+json"})

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def safe_get(url, headers=None, params=None, attempts=3, timeout=15):
    headers = headers or session.headers
    for i in range(attempts):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code == 403:
                reset = r.headers.get("X-RateLimit-Reset")
                if reset:
                    wait = max(int(reset) - int(time.time()), 1)
                    print(f"Rate limited. Sleeping {wait}s (reset).")
                    time.sleep(wait)
                else:
                    sleep = 10 * (2 ** i)
                    print(f"Rate limited. Sleeping {sleep}s.")
                    time.sleep(sleep)
            else:
                # small backoff on other failures
                time.sleep(2 * (i + 1))
        except Exception as e:
            print("Request error:", e)
            time.sleep(2 * (i + 1))
    return None

# ---------------------------
# Fetching helpers
# ---------------------------
def fetch_repos(query: str, per_page: int = PER_PAGE, page: int = 1):
    q = query if '"' in query else f'"{query}"'
    params = {
        "q": f"{q} in:name,description,readme fork:false",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }
    r = safe_get(GITHUB_SEARCH_URL, params=params)
    if r:
        return r.json().get("items", [])
    return []

def fetch_readme_raw(full_name: str) -> Optional[str]:
    url = f"{GITHUB_API_URL}/repos/{full_name}/readme"
    headers = dict(session.headers)
    headers["Accept"] = "application/vnd.github.v3.raw"
    r = safe_get(url, headers=headers)
    if r:
        return r.text.lower()
    return None

def fetch_repo_topics(full_name: str) -> List[str]:
    if not TOKEN:
        return []
    url = f"{GITHUB_API_URL}/repos/{full_name}/topics"
    headers = dict(HEADERS)
    headers.update(TOPICS_ACCEPT_HEADER)
    r = safe_get(url, headers=headers)
    if r:
        return r.json().get("names", [])
    return []

# Email extraction helpers
def get_public_email_from_user(username: str) -> Optional[str]:
    url = f"{GITHUB_API_URL}/users/{username}"
    r = safe_get(url)
    if r:
        email = r.json().get("email")
        if email and EMAIL_REGEX.search(email):
            return email
    return None

def get_email_from_readme(full_name: str) -> Optional[str]:
    text = fetch_readme_raw(full_name)
    if not text:
        return None
    mailto = re.search(r"mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text, re.IGNORECASE)
    if mailto:
        return mailto.group(1)
    plain = EMAIL_REGEX.search(text)
    if plain:
        return plain.group(0)
    return None

def get_email_from_commits(full_name: str, max_commits: int = 5) -> Optional[str]:
    url = f"{GITHUB_API_URL}/repos/{full_name}/commits"
    r = safe_get(url, params={"per_page": max_commits})
    if r:
        commits = r.json()
        for c in commits:
            commit_obj = c.get("commit", {})
            author = commit_obj.get("author", {})
            if author:
                email = author.get("email")
                if email and EMAIL_REGEX.search(email):
                    if "noreply.github" in email.lower():
                        continue
                    return email
    return None

def extract_contact_email(full_name: str, owner_username: str) -> Optional[str]:
    # Try user profile, then readme, then commits, then blog field
    email = get_public_email_from_user(owner_username)
    if email:
        return email
    time.sleep(0.12)
    email = get_email_from_readme(full_name)
    if email:
        return email
    time.sleep(0.12)
    email = get_email_from_commits(full_name)
    if email:
        return email
    # blog fallback
    url = f"{GITHUB_API_URL}/users/{owner_username}"
    r = safe_get(url)
    if r:
        blog = r.json().get("blog") or ""
        m = EMAIL_REGEX.search(blog)
        if m:
            return m.group(0)
    return None

# ---------------------------
# Relevance scoring
# ---------------------------
def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t for t in re.split(r"[^A-Za-z0-9]+", text.lower()) if t and len(t) > 1]

def keywords_from_topic(topic: str, queries: List[str]) -> List[str]:
    tokens = set(tokenize(topic))
    for q in queries:
        tokens.update(tokenize(q))
    # remove trivial tokens and common stop-like words if needed
    return sorted(tokens)

def fuzzy_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def log_scale_stars(stars: int) -> float:
    return min(1.0, math.log10(max(1, stars)) / 3.0)

def score_repo(repo: dict, topic: str, queries: List[str], readme_text: Optional[str], repo_topics: List[str]) -> float:
    name = (repo.get("name") or "").lower()
    full_name = (repo.get("full_name") or "").lower()
    desc = (repo.get("description") or "") or ""
    desc_low = desc.lower()
    readme_text = readme_text or ""
    stars = repo.get("stargazers_count", 0)
    min_stars = MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_BY_TOPIC.get("default", 0))

    keywords = keywords_from_topic(topic, queries)
    text_blob = " ".join([name, full_name, desc_low, readme_text])

    # keyword count (simple)
    keyword_hits = sum(text_blob.count(k) for k in keywords)

    # fuzzy similarity
    fuzzy_score = max(
        fuzzy_similarity(topic, name),
        fuzzy_similarity(topic, full_name),
        fuzzy_similarity(topic, desc_low),
        fuzzy_similarity(topic, readme_text[:400] if readme_text else "")
    )

    # topics match
    repo_topics_lower = [t.lower() for t in (repo_topics or [])]
    topic_matches = sum(1 for k in keywords if k in repo_topics_lower)

    # stars signal
    stars_score = log_scale_stars(stars)

    # composite score with weights (tweakable)
    score = (
        (0.50 * (0.2 * keyword_hits + 0.8 * fuzzy_score)) +  # textual match & fuzzy
        (0.25 * stars_score) +                                # popularity
        (0.20 * (topic_matches / max(1, len(keywords)))) +   # topic tag presence
        (0.05 * (1.0 if topic.lower() in text_blob else 0.0)) # literal mention boost
    )

    # penalty for forks
    if repo.get("fork"):
        score *= 0.75

    # slight boost if repo meets min_stars
    if stars >= min_stars:
        score *= 1.06

    return float(score)

# ---------------------------
# Selection logic (star-floor-first)
# ---------------------------
def select_top_by_stars_and_score(candidate_pool: List[dict], topic: str, max_per_topic: int = MAX_PER_TOPIC) -> List[dict]:
    topic_min_stars = MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_BY_TOPIC.get("default", 0))

    meets_floor = [c for c in candidate_pool if (c["repo"].get("stargazers_count", 0) or 0) >= topic_min_stars]
    below_floor = [c for c in candidate_pool if (c["repo"].get("stargazers_count", 0) or 0) < topic_min_stars]

    # sort meets by stars desc then score desc
    meets_floor.sort(key=lambda x: (x["repo"].get("stargazers_count", 0), x["score"]), reverse=True)
    below_floor.sort(key=lambda x: x["score"], reverse=True)

    top_picks = []
    # fill from meets_floor first
    for c in meets_floor:
        if len(top_picks) >= max_per_topic:
            break
        top_picks.append(c)

    # backfill from best-scored below-floor if needed
    if len(top_picks) < max_per_topic:
        needed = max_per_topic - len(top_picks)
        top_picks.extend(below_floor[:needed])

    print(f"Topic '{topic}': {len(meets_floor)} >= {topic_min_stars} stars; selected {len(top_picks)} (need {max_per_topic}) from pool {len(candidate_pool)}")
    return top_picks

# ---------------------------
# Main crawl
# ---------------------------
def crawl_all():
    all_selected = []

    for topic, queries in TOPIC_QUERIES.items():
        print("\n" + "="*60)
        print(f"🔎 Crawling topic: {topic}")
        candidate_pool = []
        seen = set()

        for q in queries:
            page = 1
            while page <= MAX_PAGES_PER_QUERY:
                repos = fetch_repos(q, per_page=PER_PAGE, page=page)
                if not repos:
                    break

                for repo in repos:
                    url = repo.get("html_url")
                    if not url or url in seen:
                        continue
                    if len(candidate_pool) >= CANDIDATE_POOL_LIMIT:
                        break

                    seen.add(url)
                    owner = repo.get("owner", {}).get("login")
                    full_name = repo.get("full_name")

                    # fetch README & topics if toggled (careful with rate limits)
                    readme = None
                    if FETCH_README:
                        time.sleep(0.2 + random.random() * 0.3)
                        readme = fetch_readme_raw(full_name)

                    repo_topics = []
                    if FETCH_TOPICS and TOKEN:
                        time.sleep(0.12 + random.random() * 0.25)
                        repo_topics = fetch_repo_topics(full_name)

                    s = score_repo(repo, topic, queries, readme, repo_topics)
                    candidate_pool.append({
                        "repo": repo,
                        "score": s,
                        "readme": readme,
                        "repo_topics": repo_topics
                    })

                page += 1
                time.sleep(REQUEST_PAUSE + random.random() * 0.8)
                if len(candidate_pool) >= CANDIDATE_POOL_LIMIT:
                    break

        if not candidate_pool:
            print(f"⚠️ No candidates for topic {topic}")
            continue

        # select top picks using star-floor-first logic
        top_picks = select_top_by_stars_and_score(candidate_pool, topic, MAX_PER_TOPIC)

        for entry in top_picks:
            repo = entry["repo"]
            owner = repo.get("owner", {}).get("login")
            full_name = repo.get("full_name")

            # extract contact email (non-invasive attempts)
            email = extract_contact_email(full_name, owner)

            selected = {
                "topic": topic,
                "name": repo.get("name"),
                "full_name": full_name,
                "url": repo.get("html_url"),
                "stars": repo.get("stargazers_count", 0),
                "description": repo.get("description"),
                "score": entry["score"],
                "email": email or "",
                "repo_topics": ",".join(entry.get("repo_topics", []))
            }
            all_selected.append(selected)
            print(f" + Selected: {selected['full_name']}  ⭐ {selected['stars']}  score={selected['score']:.3f}  email={selected['email'] or 'N/A'}")

    # save results
    df = pd.DataFrame(all_selected)
    if not df.empty:
        df = df.sort_values(by=["topic", "stars", "score"], ascending=[True, False, False])
        out_file = "repos_selected.csv"
        if DRY_RUN:
            out_file = "repos_selected_dryrun.csv"
        df.to_csv(out_file, index=False)
        print(f"\n✅ Saved {len(df)} selected repos to {out_file}")
    else:
        print("⚠️ No repos selected.")

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    crawl_all()
