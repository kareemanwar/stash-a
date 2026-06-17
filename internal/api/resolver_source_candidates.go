package api

import (
	"context"

	"github.com/stashapp/stash/pkg/models"
)

func (r *queryResolver) FindSourceCandidateScenes(ctx context.Context, sourceID string) (ret []*models.SourceCandidateScene, err error) {
	sid, err := sourceID(sourceID)
	if err != nil {
		return nil, err
	}
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Source.FindCandidateScenes(ctx, sid)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *queryResolver) FindSourceIgnoredItems(ctx context.Context, sourceID string) (ret []*models.SourceIgnoredItem, err error) {
	sid, err := sourceID(sourceID)
	if err != nil {
		return nil, err
	}
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Source.FindIgnoredItems(ctx, sid)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}
