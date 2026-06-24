package api

import (
	"context"
	"fmt"
	"time"

	"github.com/stashapp/stash/pkg/models"
)

func (r *queryResolver) saveScrapedSceneOnlineMedia(ctx context.Context, sceneID int, scraped *models.ScrapedSceneOnlineMedia) error {
	if scraped == nil {
		return nil
	}

	if scraped.EmbedURL == nil && scraped.DirectVideoURL == nil && len(scraped.Streams) == 0 {
		return nil
	}

	sourceName := scraped.SourceName
	if sourceName == "" {
		sourceName = "Unknown"
	}

	sourceSlug := scraped.SourceSlug
	if sourceSlug == "" {
		sourceSlug = "unknown"
	}

	now := time.Now().UTC()
	media := &models.SceneOnlineMedia{
		SceneID:           sceneID,
		SourceName:        sourceName,
		SourceSlug:        sourceSlug,
		ExternalID:        scraped.ExternalID,
		EmbedURL:          scraped.EmbedURL,
		DirectVideoURL:    scraped.DirectVideoURL,
		ThumbnailURL:      scraped.ThumbnailURL,
		DurationSeconds:   scraped.DurationSeconds,
		ExternalViewCount: scraped.ExternalViewCount,
		RawMetadataJSON:   scraped.RawMetadataJSON,
		LastScrapedAt:     &now,
	}

	for _, stream := range scraped.Streams {
		if stream == nil || stream.URL == "" || stream.Kind == "" {
			continue
		}

		media.Streams = append(media.Streams, &models.SceneOnlineStream{
			Label:     stream.Label,
			Kind:      stream.Kind,
			URL:       stream.URL,
			Position:  stream.Position,
			IsPrimary: stream.IsPrimary,
		})
	}

	if media.EmbedURL == nil && media.DirectVideoURL == nil && len(media.Streams) == 0 {
		return nil
	}

	return r.withTxn(ctx, func(ctx context.Context) error {
		scene, err := r.repository.Scene.Find(ctx, sceneID)
		if err != nil {
			return err
		}
		if scene == nil {
			return fmt.Errorf("scene %d not found", sceneID)
		}

		return r.repository.SceneOnlineMedia.Upsert(ctx, media)
	})
}

func (r *queryResolver) saveScrapedSceneOnlineMediaForURLs(ctx context.Context, urls []string, scraped *models.ScrapedScene) error {
	if scraped == nil || scraped.OnlineMedia == nil {
		return nil
	}

	for _, url := range uniqNonEmptyStrings(urls) {
		sceneID, err := r.findSceneIDByURL(ctx, url)
		if err != nil {
			return err
		}
		if sceneID == 0 {
			continue
		}

		return r.saveScrapedSceneOnlineMedia(ctx, sceneID, scraped.OnlineMedia)
	}

	return nil
}

func (r *queryResolver) findSceneIDByURL(ctx context.Context, url string) (int, error) {
	var sceneID int

	err := r.withReadTxn(ctx, func(ctx context.Context) error {
		result, err := r.repository.Scene.Query(ctx, models.SceneQueryOptions{
			SceneFilter: &models.SceneFilterType{
				URL: &models.StringCriterionInput{
					Value:    url,
					Modifier: models.CriterionModifierEquals,
				},
			},
		})
		if err != nil {
			return err
		}

		scenes, err := result.Resolve(ctx)
		if err != nil {
			return err
		}
		if len(scenes) > 0 {
			sceneID = scenes[0].ID
		}

		return nil
	})
	if err != nil {
		return 0, err
	}

	return sceneID, nil
}

func uniqNonEmptyStrings(values []string) []string {
	ret := make([]string, 0, len(values))
	seen := make(map[string]struct{}, len(values))
	for _, value := range values {
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		ret = append(ret, value)
	}
	return ret
}
