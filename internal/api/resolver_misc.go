package api

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"

	"github.com/stashapp/stash/internal/build"
	"github.com/stashapp/stash/internal/manager"
	"github.com/stashapp/stash/pkg/logger"
	"github.com/stashapp/stash/pkg/models"
)

func (r *queryResolver) MarkerWall(ctx context.Context, q *string) (ret []*models.SceneMarker, err error) {
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.SceneMarker.Wall(ctx, q)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *queryResolver) SceneWall(ctx context.Context, q *string) (ret []*models.Scene, err error) {
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Scene.Wall(ctx, q)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *queryResolver) MarkerStrings(ctx context.Context, q *string, sortValue *string) (ret []*models.MarkerStringsResultType, err error) {
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.SceneMarker.GetMarkerStrings(ctx, q, sortValue)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *queryResolver) Stats(ctx context.Context) (*StatsResultType, error) {
	var ret StatsResultType
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		repo := r.repository
		sceneQB := repo.Scene
		imageQB := repo.Image
		galleryQB := repo.Gallery
		studioQB := repo.Studio
		performerQB := repo.Performer
		movieQB := repo.Group
		tagQB := repo.Tag

		scenesCount, err := sceneQB.Count(ctx)
		if err != nil {
			return err
		}
		scenesSize, err := sceneQB.Size(ctx)
		if err != nil {
			return err
		}
		scenesDuration, err := sceneQB.Duration(ctx)
		if err != nil {
			return err
		}
		imageCount, err := imageQB.Count(ctx)
		if err != nil {
			return err
		}
		imageSize, err := imageQB.Size(ctx)
		if err != nil {
			return err
		}
		galleryCount, err := galleryQB.Count(ctx)
		if err != nil {
			return err
		}
		performersCount, err := performerQB.Count(ctx)
		if err != nil {
			return err
		}
		studiosCount, err := studioQB.Count(ctx)
		if err != nil {
			return err
		}
		groupsCount, err := movieQB.Count(ctx)
		if err != nil {
			return err
		}
		tagsCount, err := tagQB.Count(ctx)
		if err != nil {
			return err
		}
		scenesTotalOCount, err := sceneQB.GetAllOCount(ctx)
		if err != nil {
			return err
		}
		imagesTotalOCount, err := imageQB.OCount(ctx)
		if err != nil {
			return err
		}
		totalPlayDuration, err := sceneQB.PlayDuration(ctx)
		if err != nil {
			return err
		}
		totalPlayCount, err := sceneQB.CountAllViews(ctx)
		if err != nil {
			return err
		}
		uniqueScenePlayCount, err := sceneQB.CountUniqueViews(ctx)
		if err != nil {
			return err
		}

		ret = StatsResultType{
			SceneCount:        scenesCount,
			ScenesSize:        scenesSize,
			ScenesDuration:    scenesDuration,
			ImageCount:        imageCount,
			ImagesSize:        imageSize,
			GalleryCount:      galleryCount,
			PerformerCount:    performersCount,
			StudioCount:       studiosCount,
			GroupCount:        groupsCount,
			MovieCount:        groupsCount,
			TagCount:          tagsCount,
			TotalOCount:       scenesTotalOCount + imagesTotalOCount,
			TotalPlayDuration: totalPlayDuration,
			TotalPlayCount:    totalPlayCount,
			ScenesPlayed:      uniqueScenePlayCount,
		}
		return nil
	}); err != nil {
		return nil, err
	}
	return &ret, nil
}

func (r *queryResolver) Version(ctx context.Context) (*Version, error) {
	version, hash, buildtime := build.Version()
	return &Version{Version: &version, Hash: hash, BuildTime: buildtime}, nil
}

func (r *queryResolver) Latestversion(ctx context.Context) (*LatestVersion, error) {
	latestRelease, err := GetLatestRelease(ctx)
	if err != nil {
		if !errors.Is(err, context.Canceled) {
			logger.Errorf("Error while retrieving latest version: %v", err)
		}
		return nil, err
	}
	logger.Infof("Retrieved latest version: %s (%s)", latestRelease.Version, latestRelease.ShortHash)
	return &LatestVersion{Version: latestRelease.Version, Shorthash: latestRelease.ShortHash, ReleaseDate: latestRelease.Date, URL: latestRelease.Url}, nil
}

func (r *mutationResolver) ExecSQL(ctx context.Context, sql string, args []interface{}) (*SQLExecResult, error) {
	var rowsAffected *int64
	var lastInsertID *int64
	db := manager.GetInstance().Database
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		var err error
		rowsAffected, lastInsertID, err = db.ExecSQL(ctx, sql, args)
		return err
	}); err != nil {
		return nil, err
	}
	return &SQLExecResult{RowsAffected: rowsAffected, LastInsertID: lastInsertID}, nil
}

func (r *mutationResolver) QuerySQL(ctx context.Context, sql string, args []interface{}) (*SQLQueryResult, error) {
	var cols []string
	var rows [][]interface{}
	db := manager.GetInstance().Database
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		var err error
		cols, rows, err = db.QuerySQL(ctx, sql, args)
		return err
	}); err != nil {
		return nil, err
	}
	return &SQLQueryResult{Columns: cols, Rows: rows}, nil
}

func (r *queryResolver) SceneMarkerTags(ctx context.Context, scene_id string) ([]*SceneMarkerTag, error) {
	sceneID, err := strconv.Atoi(scene_id)
	if err != nil {
		return nil, err
	}
	var keys []int
	tags := make(map[int]*SceneMarkerTag)
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		sceneMarkers, err := r.repository.SceneMarker.FindBySceneID(ctx, sceneID)
		if err != nil {
			return err
		}
		tqb := r.repository.Tag
		for _, sceneMarker := range sceneMarkers {
			markerPrimaryTag, err := tqb.Find(ctx, sceneMarker.PrimaryTagID)
			if err != nil {
				return err
			}
			if markerPrimaryTag == nil {
				return fmt.Errorf("tag with id %d not found", sceneMarker.PrimaryTagID)
			}
			if _, hasKey := tags[markerPrimaryTag.ID]; !hasKey {
				tags[markerPrimaryTag.ID] = &SceneMarkerTag{Tag: markerPrimaryTag}
				keys = append(keys, markerPrimaryTag.ID)
			}
			tags[markerPrimaryTag.ID].SceneMarkers = append(tags[markerPrimaryTag.ID].SceneMarkers, sceneMarker)
		}
		return nil
	}); err != nil {
		return nil, err
	}
	sort.Slice(keys, func(i, j int) bool {
		return tags[keys[i]].SceneMarkers[0].Seconds < tags[keys[j]].SceneMarkers[0].Seconds
	})
	var result []*SceneMarkerTag
	for _, key := range keys {
		result = append(result, tags[key])
	}
	return result, nil
}

func firstError(errs []error) error {
	for _, e := range errs {
		if e != nil {
			return e
		}
	}
	return nil
}
