CREATE TABLE IF NOT EXISTS repositories (
    id BIGSERIAL PRIMARY KEY,
    github_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    owner_login VARCHAR(255) NOT NULL,
    stargazers_count INTEGER NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_crawled_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_repositories_stargazers ON repositories(stargazers_count);
CREATE INDEX IF NOT EXISTS idx_repositories_owner ON repositories(owner_login);