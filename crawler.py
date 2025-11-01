
"""
Faster GitHub crawler for learning resources (trimmed + optimized).
- Two-stage pipeline (prelim search, then refine top-K with README/topics)
- Prioritizes highly starred and topically-relevant repos
- Optional email extraction (lightweight: user public email and README)
- Reduced network load and tuned defaults for speed
"""

import os
import time
import math
import random
import re
import requests
import pandas as pd
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------
# Config / environment
# ---------------------------
GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_API_URL = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")  # recommended for higher rate limits
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
TOPICS_ACCEPT_HEADER = {"Accept": "application/vnd.github.mercy-preview+json"}
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# ---------------------------
# Topics (mini example — keep your full TOPIC_QUERIES)
# ---------------------------
TOPIC_QUERIES: Dict[str, List[str]] = {
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


# Per-topic minimum stars preference (tweakable)
MIN_STARS_BY_TOPIC = {
    "generative-ai": 200,
    "transformers": 150,
    "langchain": 100,
    "default": 30,
}

# ---------------------------
# Controls (tweak when experimenting)
# ---------------------------
PER_PAGE = 50                # smaller page for faster responses
MAX_PER_TOPIC = 5            # final repos per topic
CANDIDATE_POOL_LIMIT = 120   # candidate pool size per topic
MAX_PAGES_PER_QUERY = 2      # pages per single query
REFINE_TOP_K = 20            # only refine top-K candidates with README/topics
MAX_WORKERS = 8              # concurrency for README/topic fetches
FETCH_README = True          # fetch README during refinement
FETCH_TOPICS = True          # fetch repo topics during refinement (requires token)
REQUEST_PAUSE = 0.45         # small pause between search requests
DRY_RUN = True               # True => writes repos_selected_dryrun.csv
EMAIL_EXTRACTION = False     # Set True only if you need contact emails (adds requests)

# ---------------------------
# Session setup
# ---------------------------
session = requests.Session()
if HEADERS:
    session.headers.update(HEADERS)
session.headers.update({"Accept": "application/vnd.github.v3+json"})

# ---------------------------
# Networking helpers
# ---------------------------
def safe_get(url, headers=None, params=None, attempts=3, timeout=15):
    headers = headers or session.headers
    for attempt in range(attempts):
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
                    continue
                else:
                    sleep = 2 ** (attempt + 2)
                    print(f"Rate limited without reset header. Sleeping {sleep}s.")
                    time.sleep(sleep)
                    continue
            # for other 4xx/5xx, retry with backoff
            sleep = 1.5 * (attempt + 1)
            print(f"HTTP {r.status_code} for {url}. Sleeping {sleep}s then retry.")
            time.sleep(sleep)
        except Exception as e:
            sleep = 1.5 * (attempt + 1)
            print(f"Request error: {e}. Sleeping {sleep}s then retry.")
            time.sleep(sleep)
    return None

# ---------------------------
# Fetching helpers
# ---------------------------
def build_search_query(q_text: str, min_stars: int = 0) -> str:
    """
    Build a compact GitHub search query string.
    We include: text in name/description/readme and optional stars floor.
    """
    q = f'"{q_text}" in:name,description,readme fork:false'
    if min_stars and min_stars > 0:
        q += f' stars:>={min_stars}'
    return q

def fetch_repos(query: str, per_page: int = PER_PAGE, page: int = 1):
    params = {
        "q": query,
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
        # keep lowercase for faster keyword checks later
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

# ---------------------------
# Email extraction (lightweight)
# ---------------------------
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
    m = EMAIL_REGEX.search(text)
    if m:
        return m.group(0)
    # check mailto:
    mailto = re.search(r"mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text, re.IGNORECASE)
    if mailto:
        return mailto.group(1)
    return None

def extract_contact_email(full_name: str, owner_username: str) -> Optional[str]:
    # lightweight: public user email -> README email -> blog fallback
    email = get_public_email_from_user(owner_username)
    if email:
        return email
    time.sleep(0.08)
    email = get_email_from_readme(full_name)
    if email:
        return email
    # fallback to blog url on user profile (rare)
    url = f"{GITHUB_API_URL}/users/{owner_username}"
    r = safe_get(url)
    if r:
        blog = r.json().get("blog") or ""
        m = EMAIL_REGEX.search(blog)
        if m:
            return m.group(0)
    return None

# ---------------------------
# Simple scoring helpers
# ---------------------------
def log_scale_stars(stars: int) -> float:
    return min(1.0, math.log10(max(1, stars)) / 3.0)

def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t for t in re.split(r"[^A-Za-z0-9]+", text.lower()) if t and len(t) > 1]

def keywords_from_topic(topic: str, queries: List[str]) -> List[str]:
    tokens = set(tokenize(topic))
    for q in queries:
        tokens.update(tokenize(q))
    return sorted(tokens)

def fuzz_match_score(text_blob: str, keywords: List[str]) -> float:
    if not text_blob:
        return 0.0
    hits = sum(1 for k in keywords if k and k in text_blob)
    return min(1.0, hits / max(1, len(keywords)))

def prelim_score_repo(repo: dict, keywords: List[str]) -> float:
    name = (repo.get("name") or "").lower()
    full_name = (repo.get("full_name") or "").lower()
    desc = (repo.get("description") or "") or ""
    desc_low = desc.lower()
    stars_score = log_scale_stars(repo.get("stargazers_count", 0))
    blob = " ".join([name, full_name, desc_low])
    keyword_score = fuzz_match_score(blob, keywords)
    # weighted: keywords first, but stars matter
    score = 0.7 * keyword_score + 0.3 * stars_score
    if repo.get("fork"):
        score *= 0.9
    return float(score)

def refined_score_repo(repo: dict, keywords: List[str], readme_text: Optional[str], repo_topics: List[str]) -> float:
    name = (repo.get("name") or "").lower()
    full_name = (repo.get("full_name") or "").lower()
    desc_low = (repo.get("description") or "") or ""
    readme_sample = (readme_text or "")[:4000]
    blob = " ".join([name, full_name, desc_low, readme_sample])
    keyword_score = fuzz_match_score(blob, keywords)
    topic_matches = 0
    if repo_topics:
        repo_topics_lower = [t.lower() for t in repo_topics]
        topic_matches = sum(1 for k in keywords if k in repo_topics_lower)
        topic_matches = topic_matches / max(1, len(keywords))
    stars_score = log_scale_stars(repo.get("stargazers_count", 0))
    score = 0.5 * keyword_score + 0.35 * stars_score + 0.13 * topic_matches
    if repo.get("fork"):
        score *= 0.85
    return float(score)

# ---------------------------
# Parallel fetching for refinement
# ---------------------------
def _fetch_readme_and_topics_single(full_name: str) -> dict:
    readme = None
    topics = []
    try:
        if FETCH_README:
            readme = fetch_readme_raw(full_name)
    except Exception:
        readme = None
    if FETCH_TOPICS and TOKEN:
        try:
            topics = fetch_repo_topics(full_name)
        except Exception:
            topics = []
    return {"readme": readme, "topics": topics}

def fetch_readme_and_topics_parallel(full_names: List[str]) -> dict:
    out = {}
    if not full_names:
        return out
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(_fetch_readme_and_topics_single, full): full for full in full_names}
        for fut in as_completed(futures):
            full = futures[fut]
            try:
                out_val = fut.result()
            except Exception:
                out_val = {"readme": None, "topics": []}
            out[full] = out_val
            # tiny jitter to avoid bursts
            time.sleep(0.01 + random.random() * 0.03)
    return out

# ---------------------------
# Selection logic
# ---------------------------
def select_top_by_stars_and_score(candidate_pool: List[dict], topic: str, max_per_topic: int = MAX_PER_TOPIC) -> List[dict]:
    topic_min_stars = MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_BY_TOPIC.get("default", 0))
    meets_floor = [c for c in candidate_pool if (c["repo"].get("stargazers_count", 0) or 0) >= topic_min_stars]
    below_floor = [c for c in candidate_pool if (c["repo"].get("stargazers_count", 0) or 0) < topic_min_stars]

    meets_floor.sort(key=lambda x: (x["repo"].get("stargazers_count", 0), x["score"]), reverse=True)
    below_floor.sort(key=lambda x: x["score"], reverse=True)

    top_picks = []
    for c in meets_floor:
        if len(top_picks) >= max_per_topic:
            break
        top_picks.append(c)
    if len(top_picks) < max_per_topic:
        needed = max_per_topic - len(top_picks)
        top_picks.extend(below_floor[:needed])

    print(f"Topic '{topic}': {len(meets_floor)} >= {topic_min_stars} stars; selected {len(top_picks)} from pool {len(candidate_pool)}")
    return top_picks

# ---------------------------
# Main crawl (two-stage)
# ---------------------------
def crawl_all():
    all_selected = []
    for topic, queries in TOPIC_QUERIES.items():
        print("\n" + "="*60)
        print(f"🔎 Crawling topic: {topic}")
        candidate_pool = []
        seen = set()

        # Prepare keywords (used for scoring)
        keywords = keywords_from_topic(topic, queries)

        # Stage A: cheap collection + prelim scoring
        topic_min_stars = MIN_STARS_BY_TOPIC.get(topic, MIN_STARS_BY_TOPIC.get("default", 0))
        for q in queries:
            page = 1
            # build a lean search query that asks GitHub to filter by stars when possible
            query_str = build_search_query(q, min_stars=topic_min_stars if topic_min_stars >= 50 else 0)
            while page <= MAX_PAGES_PER_QUERY:
                repos = fetch_repos(query_str, per_page=PER_PAGE, page=page)
                if not repos:
                    break
                for repo in repos:
                    full_name = repo.get("full_name")
                    if not full_name or full_name in seen:
                        continue
                    seen.add(full_name)
                    if len(candidate_pool) >= CANDIDATE_POOL_LIMIT:
                        break
                    s_prelim = prelim_score_repo(repo, keywords)
                    candidate_pool.append({"repo": repo, "prelim_score": s_prelim})
                page += 1
                time.sleep(REQUEST_PAUSE + random.random() * 0.25)
                if len(candidate_pool) >= CANDIDATE_POOL_LIMIT:
                    break

        if not candidate_pool:
            print(f"⚠️ No candidates for topic {topic}")
            continue

        # Stage B: refine top-K candidates with README/topics (parallel)
        candidate_pool.sort(key=lambda x: x["prelim_score"], reverse=True)
        top_k = candidate_pool[:REFINE_TOP_K]
        full_names = [c["repo"]["full_name"] for c in top_k]
        fetched = fetch_readme_and_topics_parallel(full_names)

        refined_pool = []
        for c in top_k:
            repo = c["repo"]
            full_name = repo.get("full_name")
            readme_text = fetched.get(full_name, {}).get("readme")
            repo_topics = fetched.get(full_name, {}).get("topics", [])
            refined_s = refined_score_repo(repo, keywords, readme_text, repo_topics)
            refined_pool.append({"repo": repo, "score": refined_s, "readme": readme_text, "repo_topics": repo_topics})

        # If refined_pool is small, fill with next-best prelim candidates (without README)
        if len(refined_pool) < REFINE_TOP_K and len(candidate_pool) > REFINE_TOP_K:
            for c in candidate_pool[REFINE_TOP_K:REFINE_TOP_K + (REFINE_TOP_K - len(refined_pool))]:
                refined_pool.append({"repo": c["repo"], "score": c["prelim_score"], "readme": None, "repo_topics": []})

        # Final selection using star-floor-first logic
        top_picks = select_top_by_stars_and_score(refined_pool, topic, MAX_PER_TOPIC)

        for entry in top_picks:
            repo = entry["repo"]
            owner = repo.get("owner", {}).get("login")
            full_name = repo.get("full_name")
            email = ""
            if EMAIL_EXTRACTION:
                # optional and comparatively expensive
                try:
                    email = extract_contact_email(full_name, owner) or ""
                except Exception:
                    email = ""
                time.sleep(0.08)
            selected = {
                "topic": topic,
                "name": repo.get("name"),
                "full_name": full_name,
                "url": repo.get("html_url"),
                "stars": repo.get("stargazers_count", 0),
                "description": repo.get("description"),
                "score": entry.get("score"),
                "email": email,
                "repo_topics": ",".join(entry.get("repo_topics", []))
            }
            all_selected.append(selected)
            print(f" + Selected: {selected['full_name']}  ⭐ {selected['stars']}  score={selected['score']:.3f}  email={selected['email'] or 'N/A'}")

    # Save CSV
    df = pd.DataFrame(all_selected)
    if not df.empty:
        df = df.sort_values(by=["topic", "stars", "score"], ascending=[True, False, False])
        out_file = "repos_selected_dryrun.csv" if DRY_RUN else "repos_selected.csv"
        df.to_csv(out_file, index=False)
        print(f"\n✅ Saved {len(df)} selected repos to {out_file}")
    else:
        print("⚠️ No repos selected.")

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    crawl_all()
