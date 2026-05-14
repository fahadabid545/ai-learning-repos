# Contributing to AI Learning Repos

Contributions are welcome. This project does not accept manual edits to `README.md` or `repos.csv`.
All updates are generated programmatically by running the crawler, which ensures consistency and removes duplicates automatically.

The preferred contribution method is to run the workflow in your fork and submit a Pull Request with the updated output.

---

## How It Works

The repository has two scripts:

- `crawler.py` queries the GitHub API across 90+ AI/ML topics and saves results to `repos.csv`
- `update_readme.py` reads `repos.csv` and regenerates the categorized tables in `README.md`

A GitHub Actions workflow runs both scripts every Monday and commits the result automatically.

---

## Step-by-Step Contribution Guide

### 1. Fork the repository

Go to [https://github.com/fahadabid545/ai-learning-repos](https://github.com/fahadabid545/ai-learning-repos) and click **Fork**.

### 2. Clone your fork

```bash
git clone https://github.com/<your-username>/ai-learning-repos.git
cd ai-learning-repos
```

### 3. Enable GitHub Actions on your fork

In your fork, go to the **Actions** tab and click **Enable workflows** if prompted.

### 4. Run the update workflow

**Option A: via GitHub UI**

1. Go to **Actions** in your fork.
2. Select **Update AI Repos**.
3. Click **Run workflow**, choose the `main` branch, and confirm.
4. Wait for the workflow to complete. It will update `repos.csv` and `README.md` automatically.

**Option B: locally**

```bash
# Set up a virtual environment 
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Run the crawler 
export GITHUB_TOKEN=your_token_here   # macOS/Linux
set GITHUB_TOKEN=your_token_here      # Windows

python crawler.py
python update_readme.py
```

A GitHub personal access token is not required but is strongly recommended.
Without one, the GitHub API limits requests to 60 per hour, which will cause the crawler to pause frequently.
With a token, the limit is 5,000 per hour. Generate one at [github.com/settings/tokens](https://github.com/settings/tokens) with no special scopes needed (public repo access is sufficient).

### 5. Commit and push

```bash
git add repos.csv README.md
git commit -m "chore: update repos list"
git push origin main
```

### 6. Open a Pull Request

Go to your fork on GitHub and click **Compare & pull request**.
Include a short description of what changed or why you ran the update.

---

## Suggesting a New Topic

If you want to add a topic that is not currently covered, open an Issue with:

- The topic name
- A sample search query that returns good learning repositories for it
- The category it belongs to (see the categories in `README.md`)

---

## Notes

- Each repository appears under one topic only. The crawler deduplicates globally across all topics.
- The star count shown reflects the count at the time the crawler last ran, not real time.
- Repositories with fewer than 5 stars are excluded as noise. There is no other hard floor; the crawler takes the top results per topic regardless of absolute star count.
