package sqlite

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	"github.com/stashapp/stash/pkg/models"
)

func (qb *SourceStore) FindBySceneID(ctx context.Context, sceneID int) ([]*models.Source, error) {
	query := fmt.Sprintf(`
		SELECT s.id, s.title, s.details, s.type, s.parent_id, s.thumbnail_url,
		       s.rating100, s.favorite, s.last_synced_at, s.created_at, s.updated_at
		FROM %s s
		JOIN scenes_sources ss ON ss.source_id = s.id
		WHERE ss.scene_id = ?
		ORDER BY ss.position ASC, s.title ASC, s.id ASC`, sourcesTable)

	var sources []*models.Source
	if err := dbWrapper.Select(ctx, &sources, query, sceneID); err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	if err := qb.populateURLs(ctx, sources); err != nil {
		return nil, err
	}
	return sources, nil
}
