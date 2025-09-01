# 🤝 Contributing to AI Learning Repos

First off — thank you for thinking about contributing! 🎉  
We don’t update `README.md` or `repos.csv` manually.  
Instead, contributions happen by **running the GitHub Action in your own fork** and then submitting a Pull Request (PR) with the auto-generated updates.  

This keeps everything clean, automated, and fair. 🚀

---

## 🛠 Step-by-Step Guide

### 1. Fork this repository
- On GitHub, click the **Fork** button in the top-right.
- This creates your own copy under your account.

### 2. Clone your fork locally
```bash
# Replace <your-username> with your GitHub username
git clone https://github.com/<your-username>/ai-learning-repos.git
cd awesome-ai-learning-repos
```

### 3. Enable GitHub Actions

- In your fork, go to the Actions tab.
- Click Enable workflows if it’s disabled.

### 4. Run the update workflow
🔹 Option A: Run via GitHub UI

  - Go to Actions → Update Workflow.
  - Click Run workflow, select the branch (usually main) → Run.
  - Wait for the workflow to finish. It will update repos.csv and README.md.

🔹 Option B: Run locally (advanced)
```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate      # Mac/Linux
# OR
venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Run the crawler script
python crawler.py
```
👉 This updates repos.csv and regenerates the README.md.

### 5. Commit and push changes
```bash
git add repos.csv README.md
git commit -m "chore: update repos list"
git push origin main
```
### 6. Open a Pull Request (PR)

- On GitHub, go to your fork → click Compare & pull request.
- Write a short description of your changes (e.g., “Updated AI repos with latest stars & links”).
- Submit the Pull Request.
