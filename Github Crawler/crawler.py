import os
import time
import requests
import psycopg2
from datetime import datetime
import logging
from typing import Optional, Dict, Any, List
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitHubCrawler:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.api_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Database connection
        self.conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="postgres",
            host="localhost",
            port=5432
        )
        self.cur = self.conn.cursor()
        
        # Rate limiting
        self.rate_limit_remaining = 5000  # Initial assumption
        self.rate_limit_reset = time.time() + 3600
        
    def check_rate_limit(self):
        """Check rate limit and wait if necessary"""
        if self.rate_limit_remaining <= 10:
            sleep_time = max(self.rate_limit_reset - time.time(), 0) + 10
            logger.warning(f"Rate limit approaching. Sleeping for {sleep_time} seconds")
            time.sleep(sleep_time)
            # Reset rate limit after sleep
            self.rate_limit_remaining = 5000
    
    def execute_graphql_query(self, query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
        """Execute a GraphQL query with proper error handling and rate limiting"""
        self.check_rate_limit()
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={"query": query, "variables": variables or {}},
                timeout=60
            )
            
            # Update rate limit info
            if "x-ratelimit-remaining" in response.headers:
                self.rate_limit_remaining = int(response.headers["x-ratelimit-remaining"])
            if "x-ratelimit-reset" in response.headers:
                self.rate_limit_reset = int(response.headers["x-ratelimit-reset"])
            
            if response.status_code != 200:
                logger.error(f"GraphQL query failed with status {response.status_code}: {response.text}")
                if response.status_code == 403:  # Rate limited
                    sleep_time = max(self.rate_limit_reset - time.time(), 0) + 10
                    logger.warning(f"Rate limited. Sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
                return None
                
            data = response.json()
            
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None
                
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def fetch_repositories_by_stars(self, min_stars: int = 100, batch_size: int = 1000):
        """Fetch repositories ordered by stars"""
        query = """
        query ($cursor: String, $minStars: Int!) {
            search(
                query: "stars:>=$minStars sort:stars-desc",
                type: REPOSITORY,
                first: 100,
                after: $cursor
            ) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    ... on Repository {
                        id
                        name
                        owner {
                            login
                        }
                        stargazerCount
                        createdAt
                        updatedAt
                    }
                }
            }
            rateLimit {
                cost
                remaining
                resetAt
            }
        }
        """
        
        cursor = None
        count = 0
        target_count = 100000
        
        while count < target_count:
            variables = {
                "cursor": cursor,
                "minStars": min_stars
            }
            
            data = self.execute_graphql_query(query, variables)
            if not data:
                logger.warning("Failed to fetch data, retrying after delay")
                time.sleep(30)
                continue
                
            search_data = data["data"]["search"]
            repositories = []
            
            for node in search_data["nodes"]:
                repositories.append((
                    node["id"],
                    node["name"],
                    node["owner"]["login"],
                    node["stargazerCount"],
                    node["createdAt"],
                    node["updatedAt"],
                    datetime.now()
                ))
                count += 1
                
                if count >= target_count:
                    break
            
            # Batch insert
            self.batch_insert_repositories(repositories)
            
            if not search_data["pageInfo"]["hasNextPage"]:
                logger.info("No more pages available")
                break
                
            cursor = search_data["pageInfo"]["endCursor"]
            
            # Update min_stars to get different repositories in next iteration
            if count < target_count and len(repositories) > 0:
                min_stars = repositories[-1][3] - 1  # Last repository's star count minus one
    
    def batch_insert_repositories(self, repositories: List[tuple]):
        """Insert repositories in batches"""
        if not repositories:
            return
            
        try:
            # Use ON CONFLICT to update existing records
            self.cur.executemany(
                """
                INSERT INTO repositories (github_id, name, owner_login, stargazers_count, created_at, updated_at, last_crawled_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (github_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    owner_login = EXCLUDED.owner_login,
                    stargazers_count = EXCLUDED.stargazers_count,
                    updated_at = EXCLUDED.updated_at,
                    last_crawled_at = EXCLUDED.last_crawled_at
                """,
                repositories
            )
            self.conn.commit()
            logger.info(f"Inserted/updated {len(repositories)} repositories")
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to insert repositories: {e}")
    
    def close(self):
        """Close database connection"""
        self.cur.close()
        self.conn.close()

def main():
    crawler = GitHubCrawler()
    try:
        crawler.fetch_repositories_by_stars(min_stars=100)
    except Exception as e:
        logger.error(f"Crawler failed: {e}")
    finally:
        crawler.close()

if __name__ == "__main__":
    main()