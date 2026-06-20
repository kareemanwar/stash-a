#!/usr/bin/env python3
import json
import sqlite3
import urllib.request
from pathlib import Path

GRAPHQL = "http://127.0.0.1:9999/graphql"
OUT = Path("scripts/dev/private_debug/online_media_debug.sqlite")
SCENE_IDS = ["3420", "5629", "5628"]

QUERY = """
query($id: ID!) {
  findScene(id: $id) {
    id
    title
    url
    urls
    date
    created_at
    updated_at
    files { id path duration }
    studio { id name }
    online_media {
      embed_url
      direct_video_url
      duration_seconds
      thumbnail_url
      streams { kind label url }
    }
  }
}
"""

def gql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

if OUT.exists():
    OUT.unlink()

con = sqlite3.connect(OUT)
cur = con.cursor()

cur.executescript("""
CREATE TABLE debug_scenes (
  id TEXT PRIMARY KEY,
  title TEXT,
  url TEXT,
  urls_json TEXT,
  date TEXT,
  created_at TEXT,
  updated_at TEXT,
  studio_id TEXT,
  studio_name TEXT,
  files_json TEXT
);

CREATE TABLE debug_online_media (
  scene_id TEXT PRIMARY KEY,
  embed_url TEXT,
  direct_video_url TEXT,
  duration_seconds INTEGER,
  thumbnail_url TEXT
);

CREATE TABLE debug_online_streams (
  scene_id TEXT,
  position INTEGER,
  kind TEXT,
  label TEXT,
  url TEXT
);
""")

for scene_id in SCENE_IDS:
    data = gql(QUERY, {"id": scene_id})
    scene = data["data"]["findScene"]
    if not scene:
        continue

    studio = scene.get("studio") or {}
    media = scene.get("online_media") or {}
    streams = media.get("streams") or []

    cur.execute(
        """
        INSERT INTO debug_scenes
        (id, title, url, urls_json, date, created_at, updated_at, studio_id, studio_name, files_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scene.get("id"),
            scene.get("title"),
            scene.get("url"),
            json.dumps(scene.get("urls") or [], ensure_ascii=False),
            scene.get("date"),
            scene.get("created_at"),
            scene.get("updated_at"),
            studio.get("id"),
            studio.get("name"),
            json.dumps(scene.get("files") or [], ensure_ascii=False),
        ),
    )

    cur.execute(
        """
        INSERT INTO debug_online_media
        (scene_id, embed_url, direct_video_url, duration_seconds, thumbnail_url)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            scene.get("id"),
            media.get("embed_url"),
            media.get("direct_video_url"),
            media.get("duration_seconds"),
            media.get("thumbnail_url"),
        ),
    )

    for i, stream in enumerate(streams):
        cur.execute(
            """
            INSERT INTO debug_online_streams
            (scene_id, position, kind, label, url)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                scene.get("id"),
                i,
                stream.get("kind"),
                stream.get("label"),
                stream.get("url"),
            ),
        )

con.commit()
con.close()

print(OUT)
