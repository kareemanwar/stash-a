package api

import (
	"context"
	"fmt"
	"strings"

	"github.com/stashapp/stash/pkg/models"
)

func (r *mutationResolver) SourceUpdate(ctx context.Context, input models.SourceUpdateInput) (ret *models.Source, err error) {
	sid, err := sourceID(input.ID)
	if err != nil {
		return nil, err
	}
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		source, err := r.repository.Source.Find(ctx, sid)
		if err != nil {
			return err
		}
		if source == nil {
			return fmt.Errorf("source %d not found", sid)
		}
		if input.Title != nil {
			source.Title = strings.TrimSpace(*input.Title)
		}
		if input.Details != nil {
			source.Details = input.Details
		}
		if input.Type != nil {
			source.Type = *input.Type
		}
		if input.ThumbnailURL != nil {
			source.ThumbnailURL = input.ThumbnailURL
		}
		if input.Rating100 != nil {
			source.Rating100 = input.Rating100
		}
		if input.Favorite != nil {
			source.Favorite = *input.Favorite
		}
		if input.Urls != nil {
			source.URLs = cleanSourceURLs(input.Urls)
		}
		if err := r.repository.Source.Update(ctx, source); err != nil {
			return err
		}
		ret, err = r.repository.Source.Find(ctx, sid)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}
