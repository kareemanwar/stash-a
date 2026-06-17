package api

import (
	"context"
	"fmt"
	"strconv"
	"strings"

	"github.com/stashapp/stash/pkg/models"
)

func (r *mutationResolver) SourceCandidateSceneSave(ctx context.Context, input models.SourceCandidateSceneInput) (ret *models.SourceCandidateScene, err error) {
	sid, err := sourceID(input.SourceID)
	if err != nil {
		return nil, err
	}
	var targetSceneID *int
	if input.TargetSceneID != nil && *input.TargetSceneID != "" {
		value, err := strconv.Atoi(*input.TargetSceneID)
		if err != nil {
			return nil, fmt.Errorf("invalid target scene id %q: %w", *input.TargetSceneID, err)
		}
		targetSceneID = &value
	}
	status := models.SourceCandidateStatusNew
	if input.Status != nil {
		status = *input.Status
	}
	candidate := &models.SourceCandidateScene{
		SourceID:           sid,
		ExternalID:         input.ExternalID,
		URL:                strings.TrimSpace(input.URL),
		Title:              input.Title,
		Date:               input.Date,
		Details:            input.Details,
		ThumbnailURL:       input.ThumbnailURL,
		DurationSeconds:    input.DurationSeconds,
		Position:           input.Position,
		Status:             status,
		TargetSceneID:      targetSceneID,
		SourceSlug:         input.SourceSlug,
		RawScrapedJSON:     input.RawScrapedJSON,
		RawOnlineMediaJSON: input.RawOnlineMediaJSON,
	}
	if candidate.URL == "" {
		return nil, fmt.Errorf("candidate scene url is required")
	}
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		if err := r.repository.Source.UpsertCandidateScene(ctx, candidate); err != nil {
			return err
		}
		candidates, err := r.repository.Source.FindCandidateScenes(ctx, sid)
		if err != nil {
			return err
		}
		for _, current := range candidates {
			if current.URL == candidate.URL {
				ret = current
				return nil
			}
		}
		return nil
	}); err != nil {
		return nil, err
	}
	return ret, nil
}
