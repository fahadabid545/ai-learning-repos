import os
import time
import requests
import psycopg2
from typing import Optional, Dict, Any

GITHUB_API = "https://api.github.com/graphql"
TOKEN = os.getenv("GITHUB_TOKEN")

class GitHubCrawler:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="postgres",
            host="localhost",
            port=5432
        )
        self.cur = self.conn.cursor()
        self.rate_limit_remaining = 5000  # Initial assumption
        self.rate_limit_reset = time.time() + 3600  # Initial assumption

    def run_query(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        json_data = {"query": query, "variables": variables or {}}
        
        # Check rate limit
        current_time = time.time()
        if self.rate_limit_remaining <= 10:
            sleep_time = max(self.rate_limit_reset - current_time, 0)
            if sleep_time > 0:
                print(f"⏳ Rate limit approaching. Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time + 1)  # Add buffer
        
        response = requests.post(GITHUB_API, json=json_data, headers=headers)
        
        # Update rate limit info from headers
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
        if 'X-RateLimit-Reset' in response.headers:
            self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
        
        if response.status_code == 200:
            data = response.json()
            if 'errors' in data:
                raise Exception(f"GraphQL errors: {data['errors']}")
            return data
        elif response.status_code == 403 and 'rate limit' in response.text.lower():
            # Rate limited, wait until reset
            sleep_time = max(self.rate_limit_reset - time.time(), 0)
            print(f"⏳ Rate limited. Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time + 1)
            return self.run_query(query, variables)  # Retry
        else:
            raise Exception(f"Query failed: {response.status_code} {response.text}")

    def save_repos_batch(self, repos_data):
        """Save multiple repos in a single query for efficiency"""
        values = []
        for repo in repos_data:
            values.append(f"('{repo['name']}', {repo['stars']})")
        
        if values:
            query = """
                INSERT INTO repos (name, stars) 
                VALUES """ + ", ".join(values) + """
                ON CONFLICT (name) 
                DO UPDATE SET stars = EXCLUDED.stars
            """
            self.cur.execute(query)
            self.conn.commit()

    def crawl_repos(self, limit=100000):
        query = """
        query($cursor: String, $queryString: String!) {
            search(query: $queryString, type: REPOSITORY, first: 100, after: $cursor) {
            repositoryCount
            edges {
                node {
                ... on Repository {
                    nameWithOwner
                    stargazerCount
                }
                }
            }
            pageInfo {
                hasNextPage
                endCursor
            }
            }
        }
        """

        count = 0
        cursor = None
        batch_size = 1000  # Commit in batches for efficiency
        batch_data = []
        
        # Use a broader search query
        query_string = "size:>0"  # More inclusive than stars:>1
        
        while count < limit:
            try:
                data = self.run_query(query, {"cursor": cursor, "queryString": query_string})
                search_data = data["data"]["search"]
                repos = search_data["edges"]
                
                for edge in repos:
                    if count >= limit:
                        break
                        
                    repo = edge["node"]
                    batch_data.append({
                        "name": repo["nameWithOwner"],
                        "stars": repo["stargazerCount"]
                    })
                    count += 1
                    
                    # Commit in batches
                    if len(batch_data) >= batch_size:
                        self.save_repos_batch(batch_data)
                        batch_data = []
                        print(f"✅ Saved {count}/{limit} repositories")
                
                # Save any remaining repos in the batch
                if batch_data:
                    self.save_repos_batch(batch_data)
                    batch_data = []
                
                if not search_data["pageInfo"]["hasNextPage"]:
                    print("ℹ️ No more pages available")
                    break
                    
                cursor = search_data["pageInfo"]["endCursor"]
                
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(10)  # Wait before retrying

        print(f"✅ Crawled {count} repositories.")

    def close(self):
        self.cur.close()
        self.conn.close()

if __name__ == "__main__":
    crawler = GitHubCrawler()
    try:
        crawler.crawl_repos(100000)
    finally:
        crawler.close()