# crawler.py  (updated)
import os
import requests
import pandas as pd
import time
import random
import math
import re
from typing import Optional, List
from difflib import SequenceMatcher

GITHUB_API_URL = "https://api.github.com/search/repositories"
TOKEN = os.getenv("GITHUB_TOKEN")  # set this in env for higher rate limits
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
# Helpful preview header for repo topics
TOPICS_ACCEPT_HEADER = {"Accept": "application/vnd.github.mercy-preview+json"}

# YOUR TOPIC_QUERIES: keep your existing mapping here
TOPIC_QUERIES = {
    # ... (use your existing dict) ...
    "langchain": ["langchain tutorial", "learn langchain"],
    "generative-ai": ["generative ai tutorial", "learn generative ai"],
    "playgrounds": ["ml playground", "ai playground", "notebooks tutorial"],
    # add rest...
}

# Tunable thresholds and controls
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

PER_PAGE = 100
MAX_PER_TOPIC = 5
FETCH_README = True
FETCH_TOPICS = True            # extra API calls to fetch repo topics (helpful)
REQUEST_PAUSE = 1.0
CANDIDATE_POOL_LIMIT = 250     # how many candidate repos to collect per topic before scoring
MAX_PAGES_PER_QUERY = 3

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# session setup
session = requests.Session()
if HEADERS:
    session.headers.update(HEADERS)
session.headers.update({"Accept": "application/vnd.github.v3+json"})

def fetch_repos(query: str, per_page: int = PER_PAGE, page: int = 1):
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

def fetch_repo_topics(owner_full_name: str) -> List[str]:
    if not TOKEN:
        return []
    url = f"https://api.github.com/repos/{owner_full_name}/topics"
    headers = dict(HEADERS)
    headers.update(TOPICS_ACCEPT_HEADER)
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("names", [])
    except Exception as e:
        print("📛 topics fetch error:", e)
    return []

def get_public_email_from_user(username: str) -> Optional[str]:
    url = f"https://api.github.com/users/{username}"
    r = requests.get(url, headers=session.headers, timeout=10)
    if r.status_code == 200:
        email = r.json().get("email")
        if email and EMAIL_REGEX.search(email):
            return email
    return None

def get_email_from_readme(full_name: str) -> Optional[str]:
    text = fetch_readme_full(full_name)
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
    url = f"https://api.github.com/repos/{full_name}/commits"
    params = {"per_page": max_commits}
    r = requests.get(url, headers=session.headers, params=params, timeout=10)
    if r.status_code == 200:
        commits = r.json()
        for c in commits:
            commit_info = c.get("commit", {})
            author = commit_info.get("author", {})
            if author:
                email = author.get("email")
                if email and EMAIL_REGEX.search(email):
                    if "noreply.github" in email.lower():
                        continue
                    return email
    return None

def extract_contact_email(full_name: str, owner_username: str) -> Optional[str]:
    # orchestrate multiple strategies
    email = get_public_email_from_user(owner_username)
    if email:
        return email
    time.sleep(0.15)
    email = get_email_from_readme(full_name)
    if email:
        return email
    time.sleep(0.15)
    email = get_email_from_commits(full_name)
    if email:
        return email
    # fallback: check blog field
    url = f"https://api.github.com/users/{owner_username}"
    r = requests.get(url, headers=session.headers, timeout=10)
    if r.status_code == 200:
        blog = r.json().get("blog") or ""
        m = EMAIL_REGEX.search(blog)
        if m:
            return m.group(0)
    return None

# -------------------------
# Relevance scoring helpers
# -------------------------
def tokenize(text: str) -> List[str]:
    if not text:
        return []
    # simple tokens: split on non-alphanum, keep lowercase
    return [t for t in re.split(r"[^A-Za-z0-9]+", text.lower()) if t]

def keyword_set_from_topic_and_queries(topic: str, queries: List[str]) -> List[str]:
    tokens = set()
    tokens.update(tokenize(topic))
    for q in queries:
        tokens.update(tokenize(q))
    # remove tiny tokens
    tokens = {t for t in tokens if len(t) > 1}
    return sorted(tokens)

def fuzzy_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def log_scale_stars(stars: int) -> float:
    # returns value in [0,1] roughly — log scale to reduce dominance of very large repos
    return min(1.0, math.log10(max(1, stars)) / 3.0)  # log10(1000)=3 -> ~1

def score_repo(repo: dict, topic: str, queries: List[str], readme_text: Optional[str], repo_topics: List[str]):
    name = (repo.get("name") or "").lower()
    desc = (repo.get("description") or "") or ""
    full_name = (repo.get("full_name") or "").lower()
    desc_low = desc.lower() if desc else ""
    readme_text = (readme_text or "")
    stars = repo.get("stargazers_count", 0)
    min_stars = MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_BY_TOPIC["default"])

    # build keyword set from topic and queries (generic)
    keywords = keyword_set_from_topic_and_queries(topic, queries)

    # keyword hits count across name/desc/readme
    text_blob = " ".join([name, full_name, desc_low, readme_text])
    keyword_hits = sum(text_blob.count(k) for k in keywords)

    # fuzzy similarity: compare topic to name/desc/full_name/readme
    fuzzy_name_sim = max(
        fuzzy_similarity(topic, name),
        fuzzy_similarity(topic, full_name),
        fuzzy_similarity(topic, desc_low),
        fuzzy_similarity(topic, readme_text[:400] if readme_text else "")
    )

    # topics match boost
    topic_match = 0
    repo_topics_lower = [t.lower() for t in (repo_topics or [])]
    for k in keywords:
        if k in repo_topics_lower:
            topic_match += 1

    # stars score
    stars_score = log_scale_stars(stars)

    # combine signals with weights
    # tweak weights as needed; designed to be generic
    score = (
        (0.45 * (0.2 * keyword_hits + 0.8 * fuzzy_name_sim)) +  # name/desc/readme signals
        (0.25 * stars_score) +                                   # popularity
        (0.20 * (topic_match / max(1, len(keywords)))) +        # repo topics presence
        (0.10 * (1.0 if topic.lower() in text_blob else 0.0))    # literal topic token present
    )

    # small penalty if repo is a fork (search uses fork:false but double-check)
    if repo.get("fork"):
        score *= 0.7

    # slight boost if repo meets defined min_stars
    if stars >= min_stars:
        score *= 1.05

    return float(score)

# -------------------------
# Crawl logic using scoring
# -------------------------
def crawl_all():
    all_repos = []

    for topic, queries in TOPIC_QUERIES.items():
        print(f"\n🔎 Crawling topic: {topic}")
        seen_urls = set()
        candidate_pool = []

        for q in queries:
            page = 1
            while page <= MAX_PAGES_PER_QUERY:
                repos = fetch_repos(q, per_page=PER_PAGE, page=page)
                if not repos:
                    break

                for repo in repos:
                    url = repo.get("html_url")
                    if not url or url in seen_urls:
                        continue
                    if len(candidate_pool) >= CANDIDATE_POOL_LIMIT:
                        break

                    # minimal metadata we need immediately
                    owner = repo.get("owner", {}).get("login")
                    full_name = repo.get("full_name")

                    # optionally fetch README and topics (costly but improves scoring)
                    readme_text = None
                    if FETCH_README:
                        time.sleep(0.25 + random.random() * 0.35)
                        readme_text = fetch_readme_full(full_name)

                    repo_topics = []
                    if FETCH_TOPICS and TOKEN:
                        time.sleep(0.12 + random.random() * 0.25)
                        repo_topics = fetch_repo_topics(full_name)

                    # compute score and add to pool
                    s = score_repo(repo, topic, queries, readme_text, repo_topics)
                    candidate_pool.append({
                        "repo": repo,
                        "score": s,
                        "readme": readme_text,
                        "repo_topics": repo_topics
                    })
                    seen_urls.add(url)

                page += 1
                time.sleep(REQUEST_PAUSE + random.random() * 1.0)
                if len(candidate_pool) >= CANDIDATE_POOL_LIMIT:
                    break

        if not candidate_pool:
            print(f"⚠️ No candidates found for {topic}")
            continue

        # sort candidate pool by score desc and pick top N
        candidate_pool.sort(key=lambda x: x["score"], reverse=True)
        top_picks = candidate_pool[:MAX_PER_TOPIC]
        print(f"Picked top {len(top_picks)} repos for topic {topic} (from pool {len(candidate_pool)})")

        for entry in top_picks:
            repo = entry["repo"]
            owner = repo.get("owner", {}).get("login")
            full_name = repo.get("full_name")
            # attempt to extract contact email (optional)
            email = extract_contact_email(full_name, owner)
            all_repos.append({
                "topic": topic,
                "name": repo.get("name"),
                "full_name": full_name,
                "url": repo.get("html_url"),
                "stars": repo.get("stargazers_count", 0),
                "description": repo.get("description"),
                "score": entry["score"],
                "email": email or "",
                "repo_topics": ",".join(entry.get("repo_topics", []))
            })

    # Sort & save
    df = pd.DataFrame(all_repos)
    if not df.empty:
        df = df.sort_values(by=["topic", "score"], ascending=[True, False])
        df.to_csv("repos.csv", index=False)
        print(f"\n✅ Saved {len(df)} repos to repos.csv")
    else:
        print("⚠️ No repositories selected.")

if __name__ == "__main__":
    crawl_all()
