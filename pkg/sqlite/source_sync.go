package sqlite

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
)

func (qb *SourceStore) MarkSynced(ctx context.Context, sourceID int) error {
	query := fmt.Sprintf("UPDATE %s SET last_synced_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", sourcesTable)
	_, err := dbWrapper.Exec(ctx, query, sourceID)
	return err
}

func (qb *SourceStore) FindSceneIDByURL(ctx context.Context, url string) (*int, error) {
	trimmed := strings.TrimSpace(url)
	if trimmed == "" {
		return nil, nil
	}

	const query = `
		SELECT scene_id
		FROM scene_urls
		WHERE url = ?
		LIMIT 1`

	var sceneID int
	if err := dbWrapper.Get(ctx, &sceneID, query, trimmed); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}

	return &sceneID, nil
}
