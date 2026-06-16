package sqlite

import (
	"context"
	"fmt"

	"github.com/stashapp/stash/pkg/models"
)

const sceneOnlineMediaTable = "scene_online_media"
const sceneOnlineStreamsTable = "scene_online_streams"

type SceneOnlineMediaStore struct {
	repository
}

func NewSceneOnlineMediaStore() *SceneOnlineMediaStore {
	return &SceneOnlineMediaStore{repository: repository{tableName: sceneOnlineMediaTable, idColumn: idColumn}}
}

var _ models.SceneOnlineMediaReaderWriter = (*SceneOnlineMediaStore)(nil)

func (qb *SceneOnlineMediaStore) Find(ctx context.Context, id int) (*models.SceneOnlineMedia, error) {
	return nil, fmt.Errorf("scene online media find not implemented")
}

func (qb *SceneOnlineMediaStore) FindBySceneID(ctx context.Context, sceneID int) (*models.SceneOnlineMedia, error) {
	return nil, fmt.Errorf("scene online media find by scene id not implemented")
}

func (qb *SceneOnlineMediaStore) Upsert(ctx context.Context, media *models.SceneOnlineMedia) error {
	return fmt.Errorf("scene online media upsert not implemented")
}

func (qb *SceneOnlineMediaStore) Destroy(ctx context.Context, id int) error {
	return fmt.Errorf("scene online media destroy not implemented")
}
