package api

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"

	"github.com/99designs/gqlgen/graphql"
	"github.com/stashapp/stash/internal/build"
	"github.com/stashapp/stash/internal/manager"
	"github.com/stashapp/stash/pkg/logger"
	"github.com/stashapp/stash/pkg/models"
	"github.com/stashapp/stash/pkg/plugin/hook"
	"github.com/stashapp/stash/pkg/scraper"
)

var (
	// ErrNotImplemented is an error which means the given functionality isn't implemented by the API.
	ErrNotImplemented = errors.New("not implemented")

	// ErrNotSupported is returned whenever there's a test, which can be used to guard against the error,
	// but the given parameters aren't supported by the system.
	ErrNotSupported = errors.New("not supported")

	// ErrInput signifies errors where the input isn't valid for some reason. And no more specific error exists.
	ErrInput = errors.New("input error")
)

type hookExecutor interface {
	ExecutePostHooks(ctx context.Context, id int, hookType hook.TriggerEnum, input interface{}, inputFields []string)
}

type Resolver struct {
	repository     models.Repository
	sceneService   manager.SceneService
	imageService   manager.ImageService
	galleryService manager.GalleryService
	groupService   manager.GroupService

	hookExecutor hookExecutor
}

func (r *Resolver) scraperCache() *scraper.Cache {
	return manager.GetInstance().ScraperCache
}

func (r *Resolver) Gallery() GalleryResolver {
	return &galleryResolver{r}
}
func (r *Resolver) GalleryChapter() GalleryChapterResolver {
	return &galleryChapterResolver{r}
}
func (r *Resolver) Mutation() MutationResolver {
	return &mutationResolver{r}
}
func (r *Resolver) Performer() PerformerResolver {
	return &performerResolver{r}
}
func (r *Resolver) Query() QueryResolver {
	return &queryResolver{r}
}
func (r *Resolver) Scene() SceneResolver {
	return &sceneResolver{r}
}
func (r *Resolver) ScrapedScene() ScrapedSceneResolver {
	return &scrapedSceneResolver{r}
}
func (r *Resolver) Image() ImageResolver {
	return &imageResolver{r}
}
func (r *Resolver) SceneMarker() SceneMarkerResolver {
	return &sceneMarkerResolver{r}
}
func (r *Resolver) Studio() StudioResolver {
	return &studioResolver{r}
}

func (r *Resolver) Group() GroupResolver {
	return &groupResolver{r}
}
func (r *Resolver) Movie() MovieResolver {
	return &movieResolver{&groupResolver{r}}
}

func (r *Resolver) Subscription() SubscriptionResolver {
	return &subscriptionResolver{r}
}
func (r *Resolver) Tag() TagResolver {
	return &tagResolver{r}
}
func (r *Resolver) GalleryFile() GalleryFileResolver {
	return &galleryFileResolver{r}
}
func (r *Resolver) VideoFile() VideoFileResolver {
	return &videoFileResolver{r}
}
func (r *Resolver) ImageFile() ImageFileResolver {
	return &imageFileResolver{r}
}
func (r *Resolver) BasicFile() BasicFileResolver {
	return &basicFileResolver{r}
}
func (r *Resolver) Folder() FolderResolver {
	return &folderResolver{r}
}
func (r *Resolver) SavedFilter() SavedFilterResolver {
	return &savedFilterResolver{r}
}
func (r *Resolver) Plugin() PluginResolver {
	return &pluginResolver{r}
}
func (r *Resolver) ConfigResult() ConfigResultResolver {
	return &configResultResolver{r}
}

type mutationResolver struct{ *Resolver }
type queryResolver struct{ *Resolver }
type subscriptionResolver struct{ *Resolver }

type galleryResolver struct{ *Resolver }
type galleryChapterResolver struct{ *Resolver }
type performerResolver struct{ *Resolver }
type sceneResolver struct{ *Resolver }
type scrapedSceneResolver struct{ *Resolver }
type sceneMarkerResolver struct{ *Resolver }
type imageResolver struct{ *Resolver }
type studioResolver struct{ *Resolver }

// movie is group under the hood
type groupResolver struct{ *Resolver }
type movieResolver struct{ *groupResolver }

type tagResolver struct{ *Resolver }
type galleryFileResolver struct{ *Resolver }
type videoFileResolver struct{ *Resolver }
type imageFileResolver struct{ *Resolver }
type basicFileResolver struct{ *Resolver }
type folderResolver struct{ *Resolver }
type savedFilterResolver struct{ *Resolver }
type pluginResolver struct{ *Resolver }
type configResultResolver struct{ *Resolver }

func (r *Resolver) withTxn(ctx context.Context, fn func(ctx context.Context) error) error {
	return r.repository.WithTxn(ctx, fn)
}

func (r *Resolver) withReadTxn(ctx context.Context, fn func(ctx context.Context) error) error {
	return r.repository.WithReadTxn(ctx, fn)
}

// idOnly returns true if the query is only asking for the id field.
// This can be used to optimize certain queries where we don't need to load the full object if we're only getting the id.
func (r *Resolver) idOnly(ctx context.Context) bool {
	fields := graphql.CollectAllFields(ctx)
	return len(fields) == 1 && fields[0] == "id"
}

func (r *queryResolver) MarkerWall(ctx context.Context, q *string) (ret []*models.SceneMarker, err error) {
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.SceneMarker.Wall(ctx, q)
		return err
	}); err != nil {
		return nil, err
	}
	return ret, nil
}

func (r *queryResolver) SceneWall(ctx context.Context, q *string) (ret []*models.Scene, err error) {
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.Scene.Wall(ctx, q)
		return err
	}); err != nil {
		return nil, err
	}

	return ret, nil
}

func (r *queryResolver) MarkerStrings(ctx context.Context, q *string, sort *string) (ret []*models.MarkerStringsResultType, err error) {
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		ret, err = r.repository.SceneMarker.GetMarkerStrings(ctx, q, sort)
		return err
	}); err != nil {
		return nil, err
	}

	return ret, nil
}

func (r *queryResolver) Stats(ctx context.Context) (*StatsResultType, error) {
	var ret StatsResultType
	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		repo := r.repository
		sceneQB := repo.Scene
		imageQB := repo.Image
		galleryQB := repo.Gallery
		studioQB := repo.Studio
		performerQB := repo.Performer
		movieQB := repo.Group
		tagQB := repo.Tag

		// embrace the error
		ret.SceneCount, _ = sceneQB.Count(ctx)
		ret.SceneSize, _ = sceneQB.Size(ctx)
		ret.ScenesDuration, _ = sceneQB.Duration(ctx)

		ret.ImageCount, _ = imageQB.Count(ctx)
		ret.ImageSize, _ = imageQB.Size(ctx)

		ret.GalleryCount, _ = galleryQB.Count(ctx)
		ret.PerformerCount, _ = performerQB.Count(ctx)
		ret.StudioCount, _ = studioQB.Count(ctx)
		ret.MovieCount, _ = movieQB.Count(ctx)
		ret.GroupCount = ret.MovieCount
		ret.TagCount, _ = tagQB.Count(ctx)

		ret.TotalOCount, _ = repo.CountTotalO(ctx)
		ret.TotalPlayDuration, _ = repo.SumPlayDuration(ctx)
		ret.TotalPlayCount, _ = repo.SumPlayCount(ctx)

		ret.DatabaseSchema = strconv.Itoa(int(repo.DatabaseSchemaVersion(ctx)))
		ret.DatabasePath = repo.DatabasePath(ctx)
		ret.BackupDirectoryPath = repo.BackupDirectoryPath(ctx)
		ret.BlobsPath = repo.BlobsPath(ctx)
		ret.GeneratedPath = repo.GeneratedPath(ctx)
		ret.MetadataPath = repo.MetadataPath(ctx)
		ret.ScrapersPath = repo.ScrapersPath(ctx)
		ret.PluginsPath = repo.PluginsPath(ctx)
		ret.CachePath = repo.CachePath(ctx)

		ret.AppSchema = int(repo.AppSchemaVersion(ctx))
		ret.Status = build.GetBuildStatus()
		ret.TypicalTasks = []*TaskStatusType{}

		for _, s := range manager.JobManager.GetAllStatuses() {
			ret.TypicalTasks = append(ret.TypicalTasks, makeTaskStatus(s))
		}
		sort.Slice(ret.TypicalTasks, func(i, j int) bool { return ret.TypicalTasks[i].Name < ret.TypicalTasks[j].Name })

		return nil
	}); err != nil {
		return nil, err
	}

	return &ret, nil
}
