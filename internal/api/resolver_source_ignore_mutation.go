package api

import (
	"context"
	"strings"

	"github.com/stashapp/stash/pkg/models"
)

func (r *mutationResolver) SourceIgnoreItem(ctx context.Context, input models.SourceIgnoreItemInput) (*models.SourceIgnoredItem, error) {
	sid, err := sourceID(input.SourceID)
	if err != nil {
		return nil, err
	}
	item := &models.SourceIgnoredItem{
		SourceID:     sid,
		ContentType:  input.ContentType,
		ExternalID:   input.ExternalID,
		URL:          strings.TrimSpace(input.URL),
		Title:        input.Title,
		ThumbnailURL: input.ThumbnailURL,
		Reason:       input.Reason,
	}
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		return r.repository.Source.IgnoreItem(ctx, item)
	}); err != nil {
		return nil, err
	}
	return item, nil
}
