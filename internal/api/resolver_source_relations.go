package api

import (
	"context"

	"github.com/stashapp/stash/pkg/models"
)

func (r *sceneResolver) Sources(ctx context.Context, obj *models.Scene) (ret []*models.Source, err error) {
	if obj == nil {
		return nil, nil
	}
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Source.FindBySceneID(ctx, obj.ID)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *sourceCandidateSceneResolver) TargetScene(ctx context.Context, obj *models.SourceCandidateScene) (ret *models.Scene, err error) {
	if obj == nil || obj.TargetSceneID == nil {
		return nil, nil
	}
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Scene.Find(ctx, *obj.TargetSceneID)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}
