package api

import (
	"context"
	"strconv"

	"github.com/stashapp/stash/pkg/models"
)

func (r *sourceResolver) Parent(ctx context.Context, obj *models.Source) (ret *models.Source, err error) {
	if obj == nil || obj.ParentID == nil {
		return nil, nil
	}
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Source.Find(ctx, *obj.ParentID)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *sourceResolver) ParentID(ctx context.Context, obj *models.Source) (*string, error) {
	if obj == nil || obj.ParentID == nil {
		return nil, nil
	}
	ret := strconv.Itoa(*obj.ParentID)
	return &ret, nil
}

func (r *sourceResolver) Children(ctx context.Context, obj *models.Source) (ret []*models.Source, err error) {
	if obj == nil {
		return nil, nil
	}
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Source.FindChildren(ctx, obj.ID)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *sourceResolver) CandidateSceneCount(ctx context.Context, obj *models.Source) (int, error) {
	if obj == nil {
		return 0, nil
	}
	var candidates []*models.SourceCandidateScene
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		var err error
		candidates, err = r.repository.Source.FindCandidateScenes(ctx, obj.ID)
		return err
	}); err != nil {
		return 0, err
	}
	return len(candidates), nil
}

func (r *sourceResolver) IgnoredCount(ctx context.Context, obj *models.Source) (int, error) {
	if obj == nil {
		return 0, nil
	}
	var items []*models.SourceIgnoredItem
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		var err error
		items, err = r.repository.Source.FindIgnoredItems(ctx, obj.ID)
		return err
	}); err != nil {
		return 0, err
	}
	return len(items), nil
}
