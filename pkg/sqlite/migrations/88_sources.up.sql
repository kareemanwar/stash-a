CREATE TABLE sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title VARCHAR(255) NOT NULL,
  details TEXT,
  type VARCHAR(32) NOT NULL DEFAULT 'OTHER',
  parent_id INTEGER,
  thumbnail_url TEXT,
  rating100 INTEGER,
  favorite BOOLEAN NOT NULL DEFAULT 0,
  last_synced_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(parent_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE TABLE source_urls (
  source_id INTEGER NOT NULL,
  url TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(source_id, url),
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX index_source_urls_unique_url ON source_urls(url);
CREATE INDEX index_source_urls_source_id ON source_urls(source_id);
CREATE INDEX index_sources_parent_id ON sources(parent_id);
CREATE INDEX index_sources_title ON sources(title);

CREATE TABLE scenes_sources (
  scene_id INTEGER NOT NULL,
  source_id INTEGER NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  primary_source BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(scene_id, source_id),
  FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE INDEX index_scenes_sources_scene_id ON scenes_sources(scene_id);
CREATE INDEX index_scenes_sources_source_id ON scenes_sources(source_id);

CREATE TABLE images_sources (
  image_id INTEGER NOT NULL,
  source_id INTEGER NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  primary_source BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(image_id, source_id),
  FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE INDEX index_images_sources_image_id ON images_sources(image_id);
CREATE INDEX index_images_sources_source_id ON images_sources(source_id);

CREATE TABLE galleries_sources (
  gallery_id INTEGER NOT NULL,
  source_id INTEGER NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  primary_source BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(gallery_id, source_id),
  FOREIGN KEY(gallery_id) REFERENCES galleries(id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE INDEX index_galleries_sources_gallery_id ON galleries_sources(gallery_id);
CREATE INDEX index_galleries_sources_source_id ON galleries_sources(source_id);

CREATE TABLE groups_sources (
  group_id INTEGER NOT NULL,
  source_id INTEGER NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  primary_source BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(group_id, source_id),
  FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE INDEX index_groups_sources_group_id ON groups_sources(group_id);
CREATE INDEX index_groups_sources_source_id ON groups_sources(source_id);

CREATE TABLE source_candidate_scenes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  external_id TEXT,
  url TEXT NOT NULL,
  title TEXT,
  date DATE,
  details TEXT,
  thumbnail_url TEXT,
  duration_seconds INTEGER,
  position INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'NEW',
  target_scene_id INTEGER,
  source_slug TEXT,
  raw_scraped_json TEXT,
  raw_online_media_json TEXT,
  user_modified BOOLEAN NOT NULL DEFAULT 0,
  last_seen_at DATETIME,
  last_scraped_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY(target_scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX index_source_candidate_scenes_source_url ON source_candidate_scenes(source_id, url);
CREATE INDEX index_source_candidate_scenes_status ON source_candidate_scenes(status);
CREATE INDEX index_source_candidate_scenes_target_scene_id ON source_candidate_scenes(target_scene_id);

CREATE TABLE source_candidate_scene_tags (
  candidate_scene_id INTEGER NOT NULL,
  tag_id INTEGER,
  name TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(candidate_scene_id, name),
  FOREIGN KEY(candidate_scene_id) REFERENCES source_candidate_scenes(id) ON DELETE CASCADE,
  FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE SET NULL
);

CREATE TABLE source_candidate_scene_performers (
  candidate_scene_id INTEGER NOT NULL,
  performer_id INTEGER,
  name TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(candidate_scene_id, name),
  FOREIGN KEY(candidate_scene_id) REFERENCES source_candidate_scenes(id) ON DELETE CASCADE,
  FOREIGN KEY(performer_id) REFERENCES performers(id) ON DELETE SET NULL
);

CREATE TABLE source_candidate_scene_groups (
  candidate_scene_id INTEGER NOT NULL,
  group_id INTEGER,
  name TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(candidate_scene_id, name),
  FOREIGN KEY(candidate_scene_id) REFERENCES source_candidate_scenes(id) ON DELETE CASCADE,
  FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE SET NULL
);

CREATE TABLE source_candidate_scene_galleries (
  candidate_scene_id INTEGER NOT NULL,
  gallery_id INTEGER,
  title TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(candidate_scene_id, title),
  FOREIGN KEY(candidate_scene_id) REFERENCES source_candidate_scenes(id) ON DELETE CASCADE,
  FOREIGN KEY(gallery_id) REFERENCES galleries(id) ON DELETE SET NULL
);

CREATE TABLE source_candidate_images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  external_id TEXT,
  url TEXT NOT NULL,
  title TEXT,
  date DATE,
  details TEXT,
  thumbnail_url TEXT,
  position INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'NEW',
  target_image_id INTEGER,
  source_slug TEXT,
  raw_scraped_json TEXT,
  user_modified BOOLEAN NOT NULL DEFAULT 0,
  last_seen_at DATETIME,
  last_scraped_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY(target_image_id) REFERENCES images(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX index_source_candidate_images_source_url ON source_candidate_images(source_id, url);

CREATE TABLE source_candidate_galleries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  external_id TEXT,
  url TEXT NOT NULL,
  title TEXT,
  date DATE,
  details TEXT,
  thumbnail_url TEXT,
  position INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'NEW',
  target_gallery_id INTEGER,
  source_slug TEXT,
  raw_scraped_json TEXT,
  user_modified BOOLEAN NOT NULL DEFAULT 0,
  last_seen_at DATETIME,
  last_scraped_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY(target_gallery_id) REFERENCES galleries(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX index_source_candidate_galleries_source_url ON source_candidate_galleries(source_id, url);

CREATE TABLE source_candidate_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  external_id TEXT,
  url TEXT NOT NULL,
  title TEXT,
  date DATE,
  details TEXT,
  thumbnail_url TEXT,
  position INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'NEW',
  target_group_id INTEGER,
  source_slug TEXT,
  raw_scraped_json TEXT,
  user_modified BOOLEAN NOT NULL DEFAULT 0,
  last_seen_at DATETIME,
  last_scraped_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY(target_group_id) REFERENCES groups(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX index_source_candidate_groups_source_url ON source_candidate_groups(source_id, url);

CREATE TABLE source_candidate_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  external_id TEXT,
  url TEXT NOT NULL,
  title TEXT,
  details TEXT,
  thumbnail_url TEXT,
  type VARCHAR(32) NOT NULL DEFAULT 'OTHER',
  position INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'NEW',
  target_source_id INTEGER,
  source_slug TEXT,
  raw_scraped_json TEXT,
  user_modified BOOLEAN NOT NULL DEFAULT 0,
  last_seen_at DATETIME,
  last_scraped_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY(target_source_id) REFERENCES sources(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX index_source_candidate_sources_source_url ON source_candidate_sources(source_id, url);

CREATE TABLE source_ignored_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  content_type VARCHAR(16) NOT NULL,
  external_id TEXT,
  url TEXT NOT NULL,
  title TEXT,
  thumbnail_url TEXT,
  reason TEXT,
  ignored_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX index_source_ignored_items_source_type_url ON source_ignored_items(source_id, content_type, url);
