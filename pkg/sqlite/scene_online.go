package sqlite

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	"github.com/stashapp/stash/pkg/models"
)

const sceneOnlineMediaTable = "scene_online_media"
const sceneOnlineStreamsTable = "scene_online_streams"

type SceneOnlineMediaStore struct {
	repository
}

func NewSceneOnlineMediaStore() *SceneOnlineMediaStore {
	return &SceneOnlineMediaStore{repository: repository{tableName: sceneOnlineMediaTable, idColumn: idColumn}}
}

var _ models.SceneOnlineMediaReaderWriter = (*SceneOnlineMediaStore)(nil)

func (qb *SceneOnlineMediaStore) Find(ctx context.Context, id int) (*models.SceneOnlineMedia, error) {
	media, err := qb.find(ctx, "id = ?", id)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return media, err
}

func (qb *SceneOnlineMediaStore) FindBySceneID(ctx context.Context, sceneID int) (*models.SceneOnlineMedia, error) {
	media, err := qb.find(ctx, "scene_id = ?", sceneID)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return media, err
}

func (qb *SceneOnlineMediaStore) Upsert(ctx context.Context, media *models.SceneOnlineMedia) error {
	if media == nil {
		return fmt.Errorf("scene online media is nil")
	}

	existing, err := qb.FindBySceneID(ctx, media.SceneID)
	if err != nil {
		return err
	}

	if existing == nil {
		id, err := qb.insert(ctx, media)
		if err != nil {
			return err
		}
		media.ID = id
	} else {
		media.ID = existing.ID
		if err := qb.update(ctx, media); err != nil {
			return err
		}
	}

	if err := qb.replaceStreams(ctx, media.ID, media.Streams); err != nil {
		return err
	}

	updated, err := qb.Find(ctx, media.ID)
	if err != nil {
		return err
	}
	if updated != nil {
		*media = *updated
	}

	return nil
}

func (qb *SceneOnlineMediaStore) Destroy(ctx context.Context, id int) error {
	return qb.destroyExisting(ctx, []int{id})
}

func (qb *SceneOnlineMediaStore) find(ctx context.Context, where string, args ...interface{}) (*models.SceneOnlineMedia, error) {
	query := fmt.Sprintf(`
		SELECT id, scene_id, source_name, source_slug, external_id,
		       embed_url, direct_video_url, thumbnail_url, duration_seconds, external_view_count,
		       raw_metadata_json, last_scraped_at, created_at, updated_at
		FROM %s
		WHERE %s
		LIMIT 1`, sceneOnlineMediaTable, where)

	var media models.SceneOnlineMedia
	if err := dbWrapper.Get(ctx, &media, query, args...); err != nil {
		return nil, err
	}

	streams, err := qb.findStreams(ctx, media.ID)
	if err != nil {
		return nil, err
	}
	media.Streams = streams

	return &media, nil
}

func (qb *SceneOnlineMediaStore) findStreams(ctx context.Context, mediaID int) ([]*models.SceneOnlineStream, error) {
	query := fmt.Sprintf(`
		SELECT id, scene_online_media_id, label, kind, url, position, is_primary, created_at, updated_at
		FROM %s
		WHERE scene_online_media_id = ?
		ORDER BY position ASC, id ASC`, sceneOnlineStreamsTable)

	var streams []*models.SceneOnlineStream
	if err := dbWrapper.Select(ctx, &streams, query, mediaID); err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}

	return streams, nil
}

func (qb *SceneOnlineMediaStore) insert(ctx context.Context, media *models.SceneOnlineMedia) (int, error) {
	query := fmt.Sprintf(`
		INSERT INTO %s (
			scene_id, source_name, source_slug, external_id,
			embed_url, direct_video_url, thumbnail_url, duration_seconds, external_view_count,
			raw_metadata_json, last_scraped_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, sceneOnlineMediaTable)

	result, err := dbWrapper.Exec(ctx, query,
		media.SceneID,
		media.SourceName,
		media.SourceSlug,
		media.ExternalID,
		media.EmbedURL,
		media.DirectVideoURL,
		media.ThumbnailURL,
		media.DurationSeconds,
		media.ExternalViewCount,
		media.RawMetadataJSON,
		media.LastScrapedAt,
	)
	if err != nil {
		return 0, err
	}

	id, err := result.LastInsertId()
	if err != nil {
		return 0, err
	}

	return int(id), nil
}

func (qb *SceneOnlineMediaStore) update(ctx context.Context, media *models.SceneOnlineMedia) error {
	query := fmt.Sprintf(`
		UPDATE %s SET
			source_name = ?,
			source_slug = ?,
			external_id = ?,
			embed_url = ?,
			direct_video_url = ?,
			thumbnail_url = ?,
			duration_seconds = ?,
			external_view_count = ?,
			raw_metadata_json = ?,
			last_scraped_at = ?,
			updated_at = CURRENT_TIMESTAMP
		WHERE id = ?`, sceneOnlineMediaTable)

	_, err := dbWrapper.Exec(ctx, query,
		media.SourceName,
		media.SourceSlug,
		media.ExternalID,
		media.EmbedURL,
		media.DirectVideoURL,
		media.ThumbnailURL,
		media.DurationSeconds,
		media.ExternalViewCount,
		media.RawMetadataJSON,
		media.LastScrapedAt,
		media.ID,
	)
	return err
}

func (qb *SceneOnlineMediaStore) replaceStreams(ctx context.Context, mediaID int, streams []*models.SceneOnlineStream) error {
	deleteQuery := fmt.Sprintf("DELETE FROM %s WHERE scene_online_media_id = ?", sceneOnlineStreamsTable)
	if _, err := dbWrapper.Exec(ctx, deleteQuery, mediaID); err != nil {
		return err
	}

	if len(streams) == 0 {
		return nil
	}

	insertQuery := fmt.Sprintf(`
		INSERT INTO %s (scene_online_media_id, label, kind, url, position, is_primary)
		VALUES (?, ?, ?, ?, ?, ?)`, sceneOnlineStreamsTable)

	for i, stream := range streams {
		if stream == nil {
			continue
		}
		if stream.Position == 0 {
			stream.Position = i
		}
		stream.SceneOnlineMediaID = mediaID

		result, err := dbWrapper.Exec(ctx, insertQuery,
			stream.SceneOnlineMediaID,
			stream.Label,
			stream.Kind,
			stream.URL,
			stream.Position,
			stream.IsPrimary,
		)
		if err != nil {
			return err
		}

		id, err := result.LastInsertId()
		if err != nil {
			return err
		}
		stream.ID = int(id)
	}

	return nil
}
