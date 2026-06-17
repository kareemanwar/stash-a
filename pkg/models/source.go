package models

import (
	"context"
	"time"
)

type SourceType string

const (
	SourceTypeSite        SourceType = "SITE"
	SourceTypeSiteSection SourceType = "SITE_SECTION"
	SourceTypeSearch      SourceType = "SEARCH"
	SourceTypeCategory    SourceType = "CATEGORY"
	SourceTypeAccount     SourceType = "ACCOUNT"
	SourceTypeChannel     SourceType = "CHANNEL"
	SourceTypeProfile     SourceType = "PROFILE"
	SourceTypeCollection  SourceType = "COLLECTION"
	SourceTypeOther       SourceType = "OTHER"
)

type SourceCandidateStatus string

const (
	SourceCandidateStatusNew      SourceCandidateStatus = "NEW"
	SourceCandidateStatusLinked   SourceCandidateStatus = "LINKED"
	SourceCandidateStatusPromoted SourceCandidateStatus = "PROMOTED"
	SourceCandidateStatusIgnored  SourceCandidateStatus = "IGNORED"
	SourceCandidateStatusStale    SourceCandidateStatus = "STALE"
	SourceCandidateStatusError    SourceCandidateStatus = "ERROR"
)

type SourceIgnoredContentType string

const (
	SourceIgnoredContentTypeScene   SourceIgnoredContentType = "SCENE"
	SourceIgnoredContentTypeImage   SourceIgnoredContentType = "IMAGE"
	SourceIgnoredContentTypeGallery SourceIgnoredContentType = "GALLERY"
	SourceIgnoredContentTypeGroup   SourceIgnoredContentType = "GROUP"
	SourceIgnoredContentTypeSource  SourceIgnoredContentType = "SOURCE"
)

type Source struct {
	ID           int        `json:"id" db:"id"`
	Title        string     `json:"title" db:"title"`
	Details      *string    `json:"details" db:"details"`
	Type         SourceType `json:"type" db:"type"`
	ParentID     *int       `json:"parent_id" db:"parent_id"`
	ThumbnailURL *string    `json:"thumbnail_url" db:"thumbnail_url"`
	Rating100    *int       `json:"rating100" db:"rating100"`
	Favorite     bool       `json:"favorite" db:"favorite"`
	LastSyncedAt *time.Time `json:"last_synced_at" db:"last_synced_at"`
	CreatedAt    time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time  `json:"updated_at" db:"updated_at"`
	URLs         []string   `json:"urls" db:"-"`
}

type SourceCreateInput struct {
	Title        string     `json:"title"`
	Details      *string    `json:"details"`
	Type         SourceType `json:"type"`
	ParentID     *string    `json:"parent_id"`
	ThumbnailURL *string    `json:"thumbnail_url"`
	Rating100    *int       `json:"rating100"`
	Favorite     *bool      `json:"favorite"`
	Urls         []string   `json:"urls"`
}

type SourceUpdateInput struct {
	ID           string      `json:"id"`
	Title        *string     `json:"title"`
	Details      *string     `json:"details"`
	Type         *SourceType `json:"type"`
	ParentID     *string     `json:"parent_id"`
	ThumbnailURL *string     `json:"thumbnail_url"`
	Rating100    *int        `json:"rating100"`
	Favorite     *bool       `json:"favorite"`
	Urls         []string    `json:"urls"`
}

type SourceDestroyInput struct {
	ID string `json:"id"`
}

type SourceSyncByURLInput struct {
	SourceID *string `json:"source_id"`
	URL      string  `json:"url"`
}

type SourceSyncResult struct {
	Source              *Source                 `json:"source"`
	CandidateScenes     []*SourceCandidateScene `json:"candidate_scenes"`
	CandidateSceneCount int                     `json:"candidate_scene_count"`
	CreatedSource       bool                    `json:"created_source"`
}

type FindSourcesResultType struct {
	Count   int       `json:"count"`
	Sources []*Source `json:"sources"`
}

type SourceCandidateScene struct {
	ID                 int                        `json:"id" db:"id"`
	SourceID           int                        `json:"source_id" db:"source_id"`
	ExternalID         *string                    `json:"external_id" db:"external_id"`
	URL                string                     `json:"url" db:"url"`
	Title              *string                    `json:"title" db:"title"`
	Date               *string                    `json:"date" db:"date"`
	Details            *string                    `json:"details" db:"details"`
	ThumbnailURL       *string                    `json:"thumbnail_url" db:"thumbnail_url"`
	DurationSeconds    *int                       `json:"duration_seconds" db:"duration_seconds"`
	Position           int                        `json:"position" db:"position"`
	Status             SourceCandidateStatus      `json:"status" db:"status"`
	TargetSceneID      *int                       `json:"target_scene_id" db:"target_scene_id"`
	SourceSlug         *string                    `json:"source_slug" db:"source_slug"`
	RawScrapedJSON     *string                    `json:"raw_scraped_json" db:"raw_scraped_json"`
	RawOnlineMediaJSON *string                    `json:"raw_online_media_json" db:"raw_online_media_json"`
	UserModified       bool                       `json:"user_modified" db:"user_modified"`
	LastSeenAt         *time.Time                 `json:"last_seen_at" db:"last_seen_at"`
	LastScrapedAt      *time.Time                 `json:"last_scraped_at" db:"last_scraped_at"`
	CreatedAt          time.Time                  `json:"created_at" db:"created_at"`
	UpdatedAt          time.Time                  `json:"updated_at" db:"updated_at"`
	Tags               []*SourceCandidateRelation `json:"tags" db:"-"`
	Performers         []*SourceCandidateRelation `json:"performers" db:"-"`
	Groups             []*SourceCandidateRelation `json:"groups" db:"-"`
	Galleries          []*SourceCandidateRelation `json:"galleries" db:"-"`
}

type SourceCandidateRelation struct {
	ID       *int   `json:"id" db:"id"`
	Name     string `json:"name" db:"name"`
	Position int    `json:"position" db:"position"`
}

type SourceCandidateSceneInput struct {
	SourceID           string                          `json:"source_id"`
	ExternalID         *string                         `json:"external_id"`
	URL                string                          `json:"url"`
	Title              *string                         `json:"title"`
	Date               *string                         `json:"date"`
	Details            *string                         `json:"details"`
	ThumbnailURL       *string                         `json:"thumbnail_url"`
	DurationSeconds    *int                            `json:"duration_seconds"`
	Position           int                             `json:"position"`
	Status             *SourceCandidateStatus          `json:"status"`
	TargetSceneID      *string                         `json:"target_scene_id"`
	SourceSlug         *string                         `json:"source_slug"`
	RawScrapedJSON     *string                         `json:"raw_scraped_json"`
	RawOnlineMediaJSON *string                         `json:"raw_online_media_json"`
	Tags               []*SourceCandidateRelationInput `json:"tags"`
	Performers         []*SourceCandidateRelationInput `json:"performers"`
	Groups             []*SourceCandidateRelationInput `json:"groups"`
	Galleries          []*SourceCandidateRelationInput `json:"galleries"`
}

type SourceCandidateRelationInput struct {
	ID       *string `json:"id"`
	Name     string  `json:"name"`
	Position int     `json:"position"`
}

type SourceIgnoredItem struct {
	ID           int                      `json:"id" db:"id"`
	SourceID     int                      `json:"source_id" db:"source_id"`
	ContentType  SourceIgnoredContentType `json:"content_type" db:"content_type"`
	ExternalID   *string                  `json:"external_id" db:"external_id"`
	URL          string                   `json:"url" db:"url"`
	Title        *string                  `json:"title" db:"title"`
	ThumbnailURL *string                  `json:"thumbnail_url" db:"thumbnail_url"`
	Reason       *string                  `json:"reason" db:"reason"`
	IgnoredAt    time.Time                `json:"ignored_at" db:"ignored_at"`
	CreatedAt    time.Time                `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time                `json:"updated_at" db:"updated_at"`
}

type SourceReaderWriter interface {
	Find(ctx context.Context, id int) (*Source, error)
	FindByURL(ctx context.Context, url string) (*Source, error)
	FindBySceneID(ctx context.Context, sceneID int) ([]*Source, error)
	FindChildren(ctx context.Context, parentID int) ([]*Source, error)
	FindAll(ctx context.Context) ([]*Source, error)
	Create(ctx context.Context, source *Source) error
	Update(ctx context.Context, source *Source) error
	Destroy(ctx context.Context, id int) error
	ReplaceURLs(ctx context.Context, sourceID int, urls []string) error
	GetURLs(ctx context.Context, sourceID int) ([]string, error)
	MarkSynced(ctx context.Context, sourceID int) error
	FindCandidateScenes(ctx context.Context, sourceID int) ([]*SourceCandidateScene, error)
	UpsertCandidateScene(ctx context.Context, candidate *SourceCandidateScene) error
	FindSceneIDByURL(ctx context.Context, url string) (*int, error)
	FindIgnoredItems(ctx context.Context, sourceID int) ([]*SourceIgnoredItem, error)
	IgnoreItem(ctx context.Context, item *SourceIgnoredItem) error
	UnignoreItem(ctx context.Context, sourceID int, contentType SourceIgnoredContentType, url string) error
}
