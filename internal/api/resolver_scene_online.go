package api

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/stashapp/stash/pkg/models"
)

func sceneOnlineMediaID(id string) (int, error) {
	ret, err := strconv.Atoi(id)
	if err != nil {
		return 0, fmt.Errorf("invalid online scene id %q: %w", id, err)
	}
	return ret, nil
}

func scrapedSceneOnlineMediaForScene(obj *models.ScrapedScene) (*ScrapedSceneOnlineMedia, error) {
	raw, ok := models.GetScrapedSceneOnlineMedia(obj)
	if !ok || len(raw) == 0 {
		return nil, nil
	}

	var ret ScrapedSceneOnlineMedia
	if err := json.Unmarshal(raw, &ret); err != nil {
		return nil, err
	}
	if ret.Streams == nil {
		ret.Streams = []*ScrapedSceneOnlineStream{}
	}

	return &ret, nil
}

func (r *sceneResolver) OnlineMedia(ctx context.Context, obj *models.Scene) (ret *models.SceneOnlineMedia, err error) {
	if obj == nil {
		return nil, nil
	}

	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.SceneOnlineMedia.FindBySceneID(ctx, obj.ID)
		return err
	}); err != nil {
		return nil, err
	}

	return ret, nil
}

func (r *sceneResolver) EmbedURL(ctx context.Context, obj *models.Scene) (*string, error) {
	media, err := r.OnlineMedia(ctx, obj)
	if err != nil || media == nil {
		return nil, err
	}
	return media.EmbedURL, nil
}

func (r *sceneResolver) DirectVideoURL(ctx context.Context, obj *models.Scene) (*string, error) {
	media, err := r.OnlineMedia(ctx, obj)
	if err != nil || media == nil {
		return nil, err
	}
	return media.DirectVideoURL, nil
}

func (r *sceneResolver) DurationSeconds(ctx context.Context, obj *models.Scene) (*int, error) {
	media, err := r.OnlineMedia(ctx, obj)
	if err != nil || media == nil {
		return nil, err
	}
	return media.DurationSeconds, nil
}

func (r *sceneResolver) ExternalViewCount(ctx context.Context, obj *models.Scene) (*int, error) {
	media, err := r.OnlineMedia(ctx, obj)
	if err != nil || media == nil {
		return nil, err
	}
	return media.ExternalViewCount, nil
}

func (r *mutationResolver) SceneOnlineMediaSave(ctx context.Context, input models.SceneOnlineMediaInput) (ret *models.SceneOnlineMedia, err error) {
	sceneID, err := sceneOnlineMediaID(input.SceneID)
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	media := &models.SceneOnlineMedia{
		SceneID:           sceneID,
		SourceName:        input.SourceName,
		SourceSlug:        input.SourceSlug,
		ExternalID:        input.ExternalID,
		EmbedURL:          input.EmbedURL,
		DirectVideoURL:    input.DirectVideoURL,
		ThumbnailURL:      input.ThumbnailURL,
		DurationSeconds:   input.DurationSeconds,
		ExternalViewCount: input.ExternalViewCount,
		RawMetadataJSON:   input.RawMetadataJSON,
		LastScrapedAt:     &now,
	}

	for _, streamInput := range input.Streams {
		if streamInput == nil {
			continue
		}
		media.Streams = append(media.Streams, &models.SceneOnlineStream{
			Label:     streamInput.Label,
			Kind:      streamInput.Kind,
			URL:       streamInput.URL,
			Position:  streamInput.Position,
			IsPrimary: streamInput.IsPrimary,
		})
	}

	if err := r.withTxn(ctx, func(ctx context.Context) error {
		scene, err := r.repository.Scene.Find(ctx, sceneID)
		if err != nil {
			return err
		}
		if scene == nil {
			return fmt.Errorf("scene %d not found", sceneID)
		}

		if err := r.repository.SceneOnlineMedia.Upsert(ctx, media); err != nil {
			return err
		}
		ret = media
		return nil
	}); err != nil {
		return nil, err
	}

	return ret, nil
}

func (r *mutationResolver) SceneOnlineMediaDestroy(ctx context.Context, id string) (ret bool, err error) {
	mediaID, err := sceneOnlineMediaID(id)
	if err != nil {
		return false, err
	}

	if err := r.withTxn(ctx, func(ctx context.Context) error {
		return r.repository.SceneOnlineMedia.Destroy(ctx, mediaID)
	}); err != nil {
		return false, err
	}

	return true, nil
}
