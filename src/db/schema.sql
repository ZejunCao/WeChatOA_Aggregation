-- WeChatOA Aggregation — SQLite schema v1

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version     INTEGER PRIMARY KEY,
  applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
  name              TEXT PRIMARY KEY,
  fakeid            TEXT NOT NULL DEFAULT '',
  latest_crawl_at   TEXT,
  created_at        TEXT,
  updated_at        TEXT
);

CREATE TABLE IF NOT EXISTS articles (
  id                TEXT PRIMARY KEY,
  account_name      TEXT NOT NULL REFERENCES accounts(name),
  title             TEXT NOT NULL DEFAULT '',
  digest            TEXT NOT NULL DEFAULT '',
  link              TEXT NOT NULL DEFAULT '',
  cover_url         TEXT NOT NULL DEFAULT '',
  cover_path        TEXT,
  create_time       TEXT NOT NULL,
  create_time_unix  INTEGER,
  is_wx_deleted     INTEGER NOT NULL DEFAULT 0,
  is_user_deleted   INTEGER NOT NULL DEFAULT 0,
  item_show_type    INTEGER NOT NULL DEFAULT 0,
  llm_summary       TEXT,
  word_count        INTEGER,
  ingested_at       TEXT,
  updated_at        TEXT,
  CHECK (is_wx_deleted IN (0, 1)),
  CHECK (is_user_deleted IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_articles_account_time
  ON articles (account_name, create_time DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_articles_time
  ON articles (create_time DESC, id DESC);

CREATE TABLE IF NOT EXISTS article_bodies (
  article_id   TEXT PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
  body_text    TEXT NOT NULL,
  source_kind  TEXT NOT NULL DEFAULT 'crawl',
  fetched_at   TEXT,
  updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS article_llm_tags (
  article_id  TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  tag         TEXT NOT NULL,
  PRIMARY KEY (article_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_llm_tags_tag ON article_llm_tags (tag);

CREATE TABLE IF NOT EXISTS deleted_articles (
  article_id  TEXT PRIMARY KEY,
  deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS article_annotations (
  article_id      TEXT PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
  is_read         INTEGER NOT NULL DEFAULT 0,
  read_at         TEXT,
  starred         INTEGER NOT NULL DEFAULT 0,
  starred_at      TEXT,
  note            TEXT,
  note_updated_at TEXT,
  updated_at      TEXT,
  CHECK (is_read IN (0, 1)),
  CHECK (starred IN (0, 1))
);

CREATE TABLE IF NOT EXISTS article_user_tags (
  article_id  TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  tag         TEXT NOT NULL,
  PRIMARY KEY (article_id, tag)
);

CREATE VIRTUAL TABLE IF NOT EXISTS article_fts USING fts5(
  article_id UNINDEXED,
  title_tok,
  digest_tok,
  body_tok,
  tokenize='unicode61 remove_diacritics 0'
);
