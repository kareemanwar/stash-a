package api

import (
	"context"
	"fmt"
	"strconv"
	"strings"

	"github.com/stashapp/stash/pkg/models"
)

func sourceID(id string) (int, error) {
	ret, err := strconv.Atoi(id)
	if err != nil {
		return 0, fmt.Errorf("invalid source id %q: %w", id, err)
	}
	return ret, nil
}

func (r *queryResolver) FindSource(ctx context.Context, id string) (ret *models.Source, err error) {
	sid, err := sourceID(id)
	if err != nil {
		return nil, err
	}
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Source.Find(ctx, sid)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *queryResolver) FindSourceByURL(ctx context.Context, url string) (ret *models.Source, err error) {
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Source.FindByURL(ctx, strings.TrimSpace(url))
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}
