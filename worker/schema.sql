-- D1 schema for mevzuat-mirror.
--
-- python -m mevzuat_converter export-sql drops these tables and runs this
-- file again on every import, so the database always matches data/.
-- Field meanings are in docs/data-format.md.

CREATE TABLE documents (
  id TEXT PRIMARY KEY,                -- kanun-6098
  type TEXT NOT NULL,
  number TEXT NOT NULL,
  title TEXT NOT NULL,
  short_names TEXT NOT NULL,          -- JSON array of strings
  source_url TEXT NOT NULL,
  accepted_at TEXT,                   -- ISO date or NULL
  official_gazette_date TEXT,         -- ISO date or NULL
  official_gazette_number TEXT,
  downloaded_at TEXT NOT NULL,        -- ISO date
  latest_amendment_seen TEXT,         -- ISO date or NULL
  converter_version TEXT NOT NULL,
  article_count INTEGER NOT NULL
);

CREATE TABLE articles (
  document_id TEXT NOT NULL REFERENCES documents (id),
  ord INTEGER NOT NULL,               -- "order" in data/<id>.json
  kind TEXT NOT NULL,                 -- madde, ek_madde, gecici_madde, ...
  number TEXT NOT NULL,               -- 344, 4/A
  label TEXT NOT NULL,                -- MADDE 344
  heading TEXT,
  path TEXT NOT NULL,                 -- JSON array of strings
  repealed INTEGER NOT NULL,          -- 0 or 1
  text TEXT NOT NULL,
  notes TEXT NOT NULL,                -- JSON array of strings
  PRIMARY KEY (document_id, ord)
);

CREATE INDEX articles_by_number ON articles (document_id, kind, number);

-- Keyword search. heading and text hold normalized text, see NORMALIZATION
-- in docs/data-format.md. document_id and ord point back to articles.
CREATE VIRTUAL TABLE articles_fts USING fts5 (
  document_id UNINDEXED,
  ord UNINDEXED,
  heading,
  text,
  tokenize = 'unicode61'
);
