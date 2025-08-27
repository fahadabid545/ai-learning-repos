-- schema.sql

CREATE TABLE IF NOT EXISTS repos (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,                -- learning topic category
    name TEXT NOT NULL,                 -- repo name only (not owner)
    owner TEXT NOT NULL,                -- repo owner
    url TEXT UNIQUE NOT NULL,           -- GitHub repo URL
    stars INTEGER NOT NULL,             -- stargazer count
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_repos_topic ON repos(topic);
CREATE INDEX IF NOT EXISTS idx_repos_owner ON repos(owner);
CREATE INDEX IF NOT EXISTS idx_repos_stars ON repos(stars);
