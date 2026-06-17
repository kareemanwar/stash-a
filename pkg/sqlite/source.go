package sqlite

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"

	"github.com/stashapp/stash/pkg/models"
)

const sourcesTable = "sources"
const sourceURLsTable = "source_urls"
const sourceCandidateScenesTable = "source_candidate_scenes"
const sourceIgnoredItemsTable = "source_ignored_items"

type SourceStore struct {
	repository
}

func NewSourceStore() *SourceStore {
	return &SourceStore{repository: repository{tableName: sourcesTable, idColumn: idColumn}}
}

var _ models.SourceReaderWriter = (*SourceStore)(nil)

func (qb *SourceStore) Find(ctx context.Context, id int) (*models.Source, error) {
	source, err := qb.find(ctx, "id = ?", id)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return source, err
}

func (qb *SourceStore) FindByURL(ctx context.Context, url string) (*models.Source, error) {
	query := fmt.Sprintf(`
		SELECT s.id, s.title, s.details, s.type, s.parent_id, s.thumbnail_url,
		       s.rating100, s.favorite, s.last_synced_at, s.created_at, s.updated_at
		FROM %s s
		JOIN %s u ON u.source_id = s.id
		WHERE u.url = ?
		LIMIT 1`, sourcesTable, sourceURLsTable)

	var source models.Source
	if err := dbWrapper.Get(ctx, &source, query, url); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}

	urls, err := qb.GetURLs(ctx, source.ID)
	if err != nil {
		return nil, err
	}
	source.URLs = urls
	return &source, nil
}

func (qb *SourceStore) FindChildren(ctx context.Context, parentID int) ([]*models.Source, error) {
	query := fmt.Sprintf(`
		SELECT id, title, details, type, parent_id, thumbnail_url,
		       rating100, favorite, last_synced_at, created_at, updated_at
		FROM %s
		WHERE parent_id = ?
		ORDER BY title ASC, id ASC`, sourcesTable)

	var sources []*models.Source
	if err := dbWrapper.Select(ctx, &sources, query, parentID); err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	if err := qb.populateURLs(ctx, sources); err != nil {
		return nil, err
	}
	return sources, nil
}

func (qb *SourceStore) FindAll(ctx context.Context) ([]*models.Source, error) {
	query := fmt.Sprintf(`
		SELECT id, title, details, type, parent_id, thumbnail_url,
		       rating100, favorite, last_synced_at, created_at, updated_at
		FROM %s
		ORDER BY title ASC, id ASC`, sourcesTable)

	var sources []*models.Source
	if err := dbWrapper.Select(ctx, &sources, query); err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	if err := qb.populateURLs(ctx, sources); err != nil {
		return nil, err
	}
	return sources, nil
}

func (qb *SourceStore) Create(ctx context.Context, source *models.Source) error {
	if source == nil {
		return fmt.Errorf("source is nil")
	}
	query := fmt.Sprintf(`
		INSERT INTO %s (title, details, type, parent_id, thumbnail_url, rating100, favorite, last_synced_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)`, sourcesTable)

	result, err := dbWrapper.Exec(ctx, query,
		strings.TrimSpace(source.Title),
		source.Details,
		source.Type,
		source.ParentID,
		source.ThumbnailURL,
		source.Rating100,
		source.Favorite,
		source.LastSyncedAt,
	)
	if err != nil {
		return err
	}
	id, err := result.LastInsertId()
	if err != nil {
		return err
	}
	source.ID = int(id)
	return qb.ReplaceURLs(ctx, source.ID, source.URLs)
}

func (qb *SourceStore) Update(ctx context.Context, source *models.Source) error {
	if source == nil {
		return fmt.Errorf("source is nil")
	}
	query := fmt.Sprintf(`
		UPDATE %s SET
			title = ?, details = ?, type = ?, parent_id = ?, thumbnail_url = ?,
			rating100 = ?, favorite = ?, last_synced_at = ?, updated_at = CURRENT_TIMESTAMP
		WHERE id = ?`, sourcesTable)
	if _, err := dbWrapper.Exec(ctx, query,
		strings.TrimSpace(source.Title),
		source.Details,
		source.Type,
		source.ParentID,
		source.ThumbnailURL,
		source.Rating100,
		source.Favorite,
		source.LastSyncedAt,
		source.ID,
	); err != nil {
		return err
	}
	return qb.ReplaceURLs(ctx, source.ID, source.URLs)
}

func (qb *SourceStore) Destroy(ctx context.Context, id int) error {
	return qb.destroyExisting(ctx, []int{id})
}

func (qb *SourceStore) GetURLs(ctx context.Context, sourceID int) ([]string, error) {
	query := fmt.Sprintf(`
		SELECT url FROM %s
		WHERE source_id = ?
		ORDER BY position ASC, url ASC`, sourceURLsTable)
	var urls []string
	if err := dbWrapper.Select(ctx, &urls, query, sourceID); err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	return urls, nil
}

func (qb *SourceStore) ReplaceURLs(ctx context.Context, sourceID int, urls []string) error {
	deleteQuery := fmt.Sprintf("DELETE FROM %s WHERE source_id = ?", sourceURLsTable)
	if _, err := dbWrapper.Exec(ctx, deleteQuery, sourceID); err != nil {
		return err
	}
	insertQuery := fmt.Sprintf("INSERT INTO %s (source_id, url, position) VALUES (?, ?, ?)", sourceURLsTable)
	seen := map[string]struct{}{}
	for i, url := range urls {
		trimmed := strings.TrimSpace(url)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		if _, err := dbWrapper.Exec(ctx, insertQuery, sourceID, trimmed, i); err != nil {
			return err
		}
	}
	return nil
}

func (qb *SourceStore) FindCandidateScenes(ctx context.Context, sourceID int) ([]*models.SourceCandidateScene, error) {
	query := fmt.Sprintf(`
		SELECT id, source_id, external_id, url, title, date, details, thumbnail_url,
		       duration_seconds, position, status, target_scene_id, source_slug,
		       raw_scraped_json, raw_online_media_json, user_modified, last_seen_at,
		       last_scraped_at, created_at, updated_at
		FROM %s
		WHERE source_id = ?
		ORDER BY position ASC, id ASC`, sourceCandidateScenesTable)
	var candidates []*models.SourceCandidateScene
	if err := dbWrapper.Select(ctx, &candidates, query, sourceID); err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	return candidates, nil
}

func (qb *SourceStore) UpsertCandidateScene(ctx context.Context, candidate *models.SourceCandidateScene) error {
	if candidate == nil {
		return fmt.Errorf("source candidate scene is nil")
	}
	query := fmt.Sprintf(`
		INSERT INTO %s (
			source_id, external_id, url, title, date, details, thumbnail_url,
			duration_seconds, position, status, target_scene_id, source_slug,
			raw_scraped_json, raw_online_media_json, user_modified, last_seen_at, last_scraped_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
		ON CONFLICT(source_id, url) DO UPDATE SET
			external_id = excluded.external_id,
			title = CASE WHEN %s.user_modified THEN %s.title ELSE excluded.title END,
			date = CASE WHEN %s.user_modified THEN %s.date ELSE excluded.date END,
			details = CASE WHEN %s.user_modified THEN %s.details ELSE excluded.details END,
			thumbnail_url = CASE WHEN %s.user_modified THEN %s.thumbnail_url ELSE excluded.thumbnail_url END,
			duration_seconds = excluded.duration_seconds,
			position = excluded.position,
			status = excluded.status,
			target_scene_id = excluded.target_scene_id,
			source_slug = excluded.source_slug,
			raw_scraped_json = excluded.raw_scraped_json,
			raw_online_media_json = excluded.raw_online_media_json,
			last_seen_at = CURRENT_TIMESTAMP,
			last_scraped_at = excluded.last_scraped_at,
			updated_at = CURRENT_TIMESTAMP`, sourceCandidateScenesTable,
		sourceCandidateScenesTable, sourceCandidateScenesTable,
		sourceCandidateScenesTable, sourceCandidateScenesTable,
		sourceCandidateScenesTable, sourceCandidateScenesTable,
		sourceCandidateScenesTable, sourceCandidateScenesTable)
	_, err := dbWrapper.Exec(ctx, query,
		candidate.SourceID,
		candidate.ExternalID,
		candidate.URL,
		candidate.Title,
		candidate.Date,
		candidate.Details,
		candidate.ThumbnailURL,
		candidate.DurationSeconds,
		candidate.Position,
		candidate.Status,
		candidate.TargetSceneID,
		candidate.SourceSlug,
		candidate.RawScrapedJSON,
		candidate.RawOnlineMediaJSON,
		candidate.UserModified,
		candidate.LastScrapedAt,
	)
	return err
}

func (qb *SourceStore) FindIgnoredItems(ctx context.Context, sourceID int) ([]*models.SourceIgnoredItem, error) {
	query := fmt.Sprintf(`
		SELECT id, source_id, content_type, external_id, url, title, thumbnail_url,
		       reason, ignored_at, created_at, updated_at
		FROM %s
		WHERE source_id = ?
		ORDER BY ignored_at DESC, id DESC`, sourceIgnoredItemsTable)
	var items []*models.SourceIgnoredItem
	if err := dbWrapper.Select(ctx, &items, query, sourceID); err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	return items, nil
}

func (qb *SourceStore) IgnoreItem(ctx context.Context, item *models.SourceIgnoredItem) error {
	if item == nil {
		return fmt.Errorf("source ignored item is nil")
	}
	query := fmt.Sprintf(`
		INSERT INTO %s (source_id, content_type, external_id, url, title, thumbnail_url, reason)
		VALUES (?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(source_id, content_type, url) DO UPDATE SET
			external_id = excluded.external_id,
			title = excluded.title,
			thumbnail_url = excluded.thumbnail_url,
			reason = excluded.reason,
			ignored_at = CURRENT_TIMESTAMP,
			updated_at = CURRENT_TIMESTAMP`, sourceIgnoredItemsTable)
	_, err := dbWrapper.Exec(ctx, query,
		item.SourceID,
		item.ContentType,
		item.ExternalID,
		item.URL,
		item.Title,
		item.ThumbnailURL,
		item.Reason,
	)
	return err
}

func (qb *SourceStore) UnignoreItem(ctx context.Context, sourceID int, contentType models.SourceIgnoredContentType, url string) error {
	query := fmt.Sprintf("DELETE FROM %s WHERE source_id = ? AND content_type = ? AND url = ?", sourceIgnoredItemsTable)
	_, err := dbWrapper.Exec(ctx, query, sourceID, contentType, url)
	return err
}

func (qb *SourceStore) find(ctx context.Context, where string, args ...interface{}) (*models.Source, error) {
	query := fmt.Sprintf(`
		SELECT id, title, details, type, parent_id, thumbnail_url,
		       rating100, favorite, last_synced_at, created_at, updated_at
		FROM %s
		WHERE %s
		LIMIT 1`, sourcesTable, where)
	var source models.Source
	if err := dbWrapper.Get(ctx, &source, query, args...); err != nil {
		return nil, err
	}
	urls, err := qb.GetURLs(ctx, source.ID)
	if err != nil {
		return nil, err
	}
	source.URLs = urls
	return &source, nil
}

func (qb *SourceStore) populateURLs(ctx context.Context, sources []*models.Source) error {
	for _, source := range sources {
		if source == nil {
			continue
		}
		urls, err := qb.GetURLs(ctx, source.ID)
		if err != nil {
			return err
		}
		source.URLs = urls
	}
	return nil
}
