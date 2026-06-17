package api

import (
	"context"
	"fmt"
	"strings"

	"github.com/stashapp/stash/pkg/models"
)

func optionalSourceID(id *string) (*int, error) {
	if id == nil || *id == "" {
		return nil, nil
	}
	ret, err := sourceID(*id)
	if err != nil {
		return nil, err
	}
	return &ret, nil
}

func cleanSourceURLs(urls []string) []string {
	ret := []string{}
	seen := map[string]struct{}{}
	for _, url := range urls {
		trimmed := strings.TrimSpace(url)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		ret = append(ret, trimmed)
	}
	return ret
}

func (r *mutationResolver) SourceCreate(ctx context.Context, input models.SourceCreateInput) (ret *models.Source, err error) {
	parentID, err := optionalSourceID(input.ParentID)
	if err != nil {
		return nil, err
	}
	sourceType := input.Type
	if sourceType == "" {
		sourceType = models.SourceTypeOther
	}
	source := &models.Source{
		Title:        strings.TrimSpace(input.Title),
		Details:      input.Details,
		Type:         sourceType,
		ParentID:     parentID,
		ThumbnailURL: input.ThumbnailURL,
		Rating100:    input.Rating100,
		URLs:         cleanSourceURLs(input.Urls),
	}
	if input.Favorite != nil {
		source.Favorite = *input.Favorite
	}
	if source.Title == "" {
		return nil, fmt.Errorf("source title is required")
	}
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		if err := r.repository.Source.Create(ctx, source); err != nil {
			return err
		}
		ret, err = r.repository.Source.Find(ctx, source.ID)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}
