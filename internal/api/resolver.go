package api

import (
	"context"
	"errors"

	"github.com/99designs/gqlgen/graphql"
	"github.com/stashapp/stash/internal/manager"
	"github.com/stashapp/stash/pkg/models"
	"github.com/stashapp/stash/pkg/plugin/hook"
	"github.com/stashapp/stash/pkg/scraper"
)

var (
	ErrNotImplemented = errors.New("not implemented")
	ErrNotSupported   = errors.New("not supported")
	ErrInput          = errors.New("input error")
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
	hookExecutor   hookExecutor
}

func (r *Resolver) scraperCache() *scraper.Cache { return manager.GetInstance().ScraperCache }
func (r *Resolver) Gallery() GalleryResolver { return &galleryResolver{r} }
func (r *Resolver) GalleryChapter() GalleryChapterResolver { return &galleryChapterResolver{r} }
func (r *Resolver) Mutation() MutationResolver { return &mutationResolver{r} }
func (r *Resolver) Performer() PerformerResolver { return &performerResolver{r} }
func (r *Resolver) Query() QueryResolver { return &queryResolver{r} }
func (r *Resolver) Scene() SceneResolver { return &sceneResolver{r} }
func (r *Resolver) ScrapedScene() ScrapedSceneResolver { return &scrapedSceneResolver{r} }
func (r *Resolver) Source() SourceResolver { return &sourceResolver{r} }
func (r *Resolver) Image() ImageResolver { return &imageResolver{r} }
func (r *Resolver) SceneMarker() SceneMarkerResolver { return &sceneMarkerResolver{r} }
func (r *Resolver) Studio() StudioResolver { return &studioResolver{r} }
func (r *Resolver) Group() GroupResolver { return &groupResolver{r} }
func (r *Resolver) Movie() MovieResolver { return &movieResolver{&groupResolver{r}} }
func (r *Resolver) Subscription() SubscriptionResolver { return &subscriptionResolver{r} }
func (r *Resolver) Tag() TagResolver { return &tagResolver{r} }
func (r *Resolver) GalleryFile() GalleryFileResolver { return &galleryFileResolver{r} }
func (r *Resolver) VideoFile() VideoFileResolver { return &videoFileResolver{r} }
func (r *Resolver) ImageFile() ImageFileResolver { return &imageFileResolver{r} }
func (r *Resolver) BasicFile() BasicFileResolver { return &basicFileResolver{r} }
func (r *Resolver) Folder() FolderResolver { return &folderResolver{r} }
func (r *Resolver) SavedFilter() SavedFilterResolver { return &savedFilterResolver{r} }
func (r *Resolver) Plugin() PluginResolver { return &pluginResolver{r} }
func (r *Resolver) ConfigResult() ConfigResultResolver { return &configResultResolver{r} }

type mutationResolver struct{ *Resolver }
type queryResolver struct{ *Resolver }
type subscriptionResolver struct{ *Resolver }
type galleryResolver struct{ *Resolver }
type galleryChapterResolver struct{ *Resolver }
type performerResolver struct{ *Resolver }
type sceneResolver struct{ *Resolver }
type scrapedSceneResolver struct{ *Resolver }
type sourceResolver struct{ *Resolver }
type sceneMarkerResolver struct{ *Resolver }
type imageResolver struct{ *Resolver }
type studioResolver struct{ *Resolver }
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

func (r *Resolver) withTxn(ctx context.Context, fn func(ctx context.Context) error) error { return r.repository.WithTxn(ctx, fn) }
func (r *Resolver) withReadTxn(ctx context.Context, fn func(ctx context.Context) error) error { return r.repository.WithReadTxn(ctx, fn) }
func (r *Resolver) idOnly(ctx context.Context) bool {
	fields := graphql.CollectAllFields(ctx)
	return len(fields) == 1 && fields[0] == "id"
}
func (r *scrapedSceneResolver) OnlineMedia(ctx context.Context, obj *models.ScrapedScene) (*ScrapedSceneOnlineMedia, error) {
	return scrapedSceneOnlineMediaForScene(obj)
}
