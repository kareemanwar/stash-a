package models

import (
	"context"
	"time"
)

// SceneOnlineMedia stores provider/remote playback metadata for a Scene.
// Native Scene fields keep user-facing metadata such as title, urls, date,
// studio, tags, performers, and cover image. This model owns online-only
// playback/provider data such as embed URLs, direct video URLs, external view
// counts, remote thumbnails, and provider stream variants.
type SceneOnlineMedia struct {
	ID                int                  `json:"id" db:"id"`
	SceneID           int                  `json:"scene_id" db:"scene_id"`
	SourceName        string               `json:"source_name" db:"source_name"`
	SourceSlug        string               `json:"source_slug" db:"source_slug"`
	ExternalID        *string              `json:"external_id" db:"external_id"`
	PageURL           string               `json:"page_url" db:"page_url"`
	CanonicalURL      *string              `json:"canonical_url" db:"canonical_url"`
	EmbedURL          *string              `json:"embed_url" db:"embed_url"`
	DirectVideoURL    *string              `json:"direct_video_url" db:"direct_video_url"`
	ThumbnailURL      *string              `json:"thumbnail_url" db:"thumbnail_url"`
	DurationSeconds   *int                 `json:"duration_seconds" db:"duration_seconds"`
	ExternalViewCount *int                 `json:"external_view_count" db:"external_view_count"`
	RawMetadataJSON   *string              `json:"raw_metadata_json" db:"raw_metadata_json"`
	LastScrapedAt     *time.Time           `json:"last_scraped_at" db:"last_scraped_at"`
	CreatedAt         time.Time            `json:"created_at" db:"created_at"`
	UpdatedAt         time.Time            `json:"updated_at" db:"updated_at"`
	Streams           []*SceneOnlineStream `json:"streams,omitempty" db:"-"`
}

// SceneOnlineStream stores a playable stream variant for an online scene.
type SceneOnlineStream struct {
	ID                 int       `json:"id" db:"id"`
	SceneOnlineMediaID int       `json:"scene_online_media_id" db:"scene_online_media_id"`
	Label              *string   `json:"label" db:"label"`
	Kind               string    `json:"kind" db:"kind"`
	URL                string    `json:"url" db:"url"`
	Position           int       `json:"position" db:"position"`
	IsPrimary          bool      `json:"is_primary" db:"is_primary"`
	CreatedAt          time.Time `json:"created_at" db:"created_at"`
	UpdatedAt          time.Time `json:"updated_at" db:"updated_at"`
}

// SceneOnlineMediaInput is used by GraphQL mutations to create or update
// online playback/provider metadata for a scene.
type SceneOnlineMediaInput struct {
	SceneID           string                    `json:"scene_id"`
	SourceName        string                    `json:"source_name"`
	SourceSlug        string                    `json:"source_slug"`
	ExternalID        *string                   `json:"external_id"`
	PageURL           string                    `json:"page_url"`
	CanonicalURL      *string                   `json:"canonical_url"`
	EmbedURL          *string                   `json:"embed_url"`
	DirectVideoURL    *string                   `json:"direct_video_url"`
	ThumbnailURL      *string                   `json:"thumbnail_url"`
	DurationSeconds   *int                      `json:"duration_seconds"`
	ExternalViewCount *int                      `json:"external_view_count"`
	RawMetadataJSON   *string                   `json:"raw_metadata_json"`
	Streams           []*SceneOnlineStreamInput `json:"streams"`
}

// SceneOnlineStreamInput is used by GraphQL mutations to create/update stream
// variants for a SceneOnlineMedia record.
type SceneOnlineStreamInput struct {
	Label     *string `json:"label"`
	Kind      string  `json:"kind"`
	URL       string  `json:"url"`
	Position  int     `json:"position"`
	IsPrimary bool    `json:"is_primary"`
}

type SceneOnlineMediaReader interface {
	Find(ctx context.Context, id int) (*SceneOnlineMedia, error)
	FindBySceneID(ctx context.Context, sceneID int) (*SceneOnlineMedia, error)
}

type SceneOnlineMediaWriter interface {
	Upsert(ctx context.Context, media *SceneOnlineMedia) error
	Destroy(ctx context.Context, id int) error
}

type SceneOnlineMediaReaderWriter interface {
	SceneOnlineMediaReader
	SceneOnlineMediaWriter
}
