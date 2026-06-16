package sqlite

import "github.com/stashapp/stash/pkg/models"

const sceneOnlineMediaTable = "scene_online_media"

type SceneOnlineMediaStore struct {
	repository
}

func NewSceneOnlineMediaStore() *SceneOnlineMediaStore {
	return &SceneOnlineMediaStore{repository: repository{tableName: sceneOnlineMediaTable, idColumn: idColumn}}
}

var _ models.SceneOnlineMediaReaderWriter = (*SceneOnlineMediaStore)(nil)
