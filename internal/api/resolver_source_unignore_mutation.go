package api

import (
	"context"
	"strings"

	"github.com/stashapp/stash/pkg/models"
)

func (r *mutationResolver) SourceUnignoreItem(ctx context.Context, input models.SourceUnignoreItemInput) (bool, error) {
	sid, err := sourceID(input.SourceID)
	if err != nil {
		return false, err
	}
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		return r.repository.Source.UnignoreItem(ctx, sid, input.ContentType, strings.TrimSpace(input.URL))
	}); err != nil {
		return false, err
	}
	return true, nil
}
