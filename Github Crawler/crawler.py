import os
import time
import requests
import psycopg2
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
API_URL = "https://api.github.com/graphql"

conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="postgres",
    host="localhost",
    port=5432
)
cur = conn.cursor()

# Basic GraphQL search (we’ll loop pages)
# Note: Search returns up to 1000 results per query; this simple version just shows the flow.
query = """
query ($cursor: String) {
    search(query: "stars:>1", type: REPOSITORY, first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { ... on Repository { nameWithOwner stargazerCount } }
    }
}
"""

def fetch_repos(target=100000):
    cursor = None
    count = 0
    while count < target:
        r = requests.post(
            API_URL,
            headers={"Authorization": f"bearer {GITHUB_TOKEN}"},
            json={"query": query, "variables": {"cursor": cursor}},
            timeout=60
        )
        if r.status_code != 200:
            time.sleep(10)
            continue

        payload = r.json()
        if "errors" in payload:
            # Simple rate limit/backoff handling
            time.sleep(30)
            continue

        data = payload["data"]["search"]
        for repo in data["nodes"]:
            cur.execute(
                """
                INSERT INTO repos (name, stars, last_updated)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    stars = EXCLUDED.stars,
                    last_updated = EXCLUDED.last_updated;
                """,
                (repo["nameWithOwner"], repo["stargazerCount"], datetime.now())
            )
            count += 1
            if count >= target:
                break

        conn.commit()
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]

if __name__ == "__main__":
    fetch_repos()
    print("✅ Done")
