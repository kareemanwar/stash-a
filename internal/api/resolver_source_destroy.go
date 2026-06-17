package api

import (
	"context"

	"github.com/stashapp/stash/pkg/models"
)

func (r *mutationResolver) SourceDestroy(ctx context.Context, input models.SourceDestroyInput) (bool, error) {
	sid, err := sourceID(input.ID)
	if err != nil {
		return false, err
	}
	if err := r.withTxn(ctx, func(ctx context.Context) error {
		return r.repository.Source.Destroy(ctx, sid)
	}); err != nil {
		return false, err
	}
	return true, nil
}
