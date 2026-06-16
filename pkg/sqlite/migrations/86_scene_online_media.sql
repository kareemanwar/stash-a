CREATE TABLE scene_online_media (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scene_id INTEGER NOT NULL UNIQUE,
  source_name TEXT NOT NULL,
  source_slug TEXT NOT NULL,
  external_id TEXT,
  page_url TEXT NOT NULL,
  canonical_url TEXT,
  embed_url TEXT,
  direct_video_url TEXT,
  thumbnail_url TEXT,
  duration_seconds INTEGER,
  external_view_count INTEGER,
  raw_metadata_json TEXT,
  last_scraped_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

CREATE INDEX index_scene_online_media_scene_id ON scene_online_media(scene_id);
CREATE INDEX index_scene_online_media_source_slug ON scene_online_media(source_slug);

CREATE TABLE scene_online_streams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scene_online_media_id INTEGER NOT NULL,
  label TEXT,
  kind TEXT NOT NULL,
  url TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(scene_online_media_id) REFERENCES scene_online_media(id) ON DELETE CASCADE
);

CREATE INDEX index_scene_online_streams_media_id ON scene_online_streams(scene_online_media_id);
