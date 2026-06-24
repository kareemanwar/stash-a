package api

import (
	"context"
	"errors"
	"fmt"
	"slices"
	"strconv"
	"strings"

	"github.com/stashapp/stash/pkg/match"
	"github.com/stashapp/stash/pkg/models"
	"github.com/stashapp/stash/pkg/scraper"
	"github.com/stashapp/stash/pkg/sliceutil"
	"github.com/stashapp/stash/pkg/sliceutil/stringslice"
)

func (r *queryResolver) ScrapeURL(ctx context.Context, url string, ty scraper.ScrapeContentType) (scraper.ScrapedContent, error) {
	return r.scraperCache().ScrapeURL(ctx, url, ty)
}

func (r *queryResolver) ListScrapers(ctx context.Context, types []scraper.ScrapeContentType) ([]*scraper.Scraper, error) {
	return r.scraperCache().ListScrapers(types), nil
}

func (r *queryResolver) ScrapePerformerURL(ctx context.Context, url string) (*models.ScrapedPerformer, error) {
	content, err := r.scraperCache().ScrapeURL(ctx, url, scraper.ScrapeContentTypePerformer)
	if err != nil {
		return nil, err
	}

	return marshalScrapedPerformer(content)
}

func (r *queryResolver) ScrapeSceneQuery(ctx context.Context, scraperID string, query string) ([]*models.ScrapedScene, error) {
	if query == "" {
		return nil, nil
	}

	content, err := r.scraperCache().ScrapeName(ctx, scraperID, query, scraper.ScrapeContentTypeScene)
	if err != nil {
		return nil, err
	}

	ret, err := marshalScrapedScenes(content)
	if err != nil {
		return nil, err
	}

	return ret, nil
}

func (r *queryResolver) ScrapeSceneURL(ctx context.Context, url string) (*models.ScrapedScene, error) {
	content, err := r.scraperCache().ScrapeURL(ctx, url, scraper.ScrapeContentTypeScene)
	if err != nil {
		return nil, err
	}

	ret, err := marshalScrapedScene(content)
	if err != nil {
		return nil, err
	}

	if ret != nil {
		urls := append([]string{url}, ret.URLs...)
		if err := r.saveScrapedSceneOnlineMediaForURLs(ctx, urls, ret); err != nil {
			return nil, err
		}
	}

	return ret, nil
}

func (r *queryResolver) ScrapeGalleryURL(ctx context.Context, url string) (*models.ScrapedGallery, error) {
	content, err := r.scraperCache().ScrapeURL(ctx, url, scraper.ScrapeContentTypeGallery)
	if err != nil {
		return nil, err
	}

	ret, err := marshalScrapedGallery(content)
	if err != nil {
		return nil, err
	}

	return ret, nil
}

func (r *queryResolver) ScrapeImageURL(ctx context.Context, url string) (*models.ScrapedImage, error) {
	content, err := r.scraperCache().ScrapeURL(ctx, url, scraper.ScrapeContentTypeImage)
	if err != nil {
		return nil, err
	}

	return marshalScrapedImage(content)
}

func (r *queryResolver) ScrapeMovieURL(ctx context.Context, url string) (*models.ScrapedMovie, error) {
	content, err := r.scraperCache().ScrapeURL(ctx, url, scraper.ScrapeContentTypeMovie)
	if err != nil {
		return nil, err
	}

	ret, err := marshalScrapedMovie(content)
	if err != nil {
		return nil, err
	}

	return ret, nil
}

func (r *queryResolver) ScrapeGroupURL(ctx context.Context, url string) (*models.ScrapedGroup, error) {
	content, err := r.scraperCache().ScrapeURL(ctx, url, scraper.ScrapeContentTypeGroup)
	if err != nil {
		return nil, err
	}

	ret, err := marshalScrapedGroup(content)
	if err != nil {
		return nil, err
	}

	// convert to scraped group
	group := &models.ScrapedGroup{
		StoredID:   ret.StoredID,
		Name:       ret.Name,
		Aliases:    ret.Aliases,
		Duration:   ret.Duration,
		Date:       ret.Date,
		Rating:     ret.Rating,
		Director:   ret.Director,
		URLs:       ret.URLs,
		Synopsis:   ret.Synopsis,
		Studio:     ret.Studio,
		Tags:       ret.Tags,
		FrontImage: ret.FrontImage,
		BackImage:  ret.BackImage,
	}

	return group, nil
}

func (r *queryResolver) ScrapeSingleScene(ctx context.Context, source scraper.Source, input ScrapeSingleSceneInput) ([]*models.ScrapedScene, error) {
	var ret []*models.ScrapedScene

	var sceneID int
	if input.SceneID != nil {
		var err error
		sceneID, err = strconv.Atoi(*input.SceneID)
		if err != nil {
			return nil, fmt.Errorf("%w: sceneID is not an integer: '%s'", ErrInput, *input.SceneID)
		}
	}

	switch {
	case source.ScraperID != nil:
		var err error
		var c scraper.ScrapedContent
		var content []scraper.ScrapedContent

		switch {
		case input.SceneID != nil:
			c, err = r.scraperCache().ScrapeID(ctx, *source.ScraperID, sceneID, scraper.ScrapeContentTypeScene)
			if c != nil {
				content = []scraper.ScrapedContent{c}
			}
		case input.SceneInput != nil:
			c, err = r.scraperCache().ScrapeFragment(ctx, *source.ScraperID, scraper.Input{Scene: input.SceneInput})
			if c != nil {
				content = []scraper.ScrapedContent{c}
			}
		case input.Query != nil:
			content, err = r.scraperCache().ScrapeName(ctx, *source.ScraperID, *input.Query, scraper.ScrapeContentTypeScene)
		default:
			err = fmt.Errorf("%w: scene_id, scene_input, or query must be set", ErrInput)
		}

		if err != nil {
			return nil, err
		}

		ret, err = marshalScrapedScenes(content)
		if err != nil {
			return nil, err
		}
	case source.StashBoxIndex != nil || source.StashBoxEndpoint != nil:
		b, err := resolveStashBox(source.StashBoxIndex, source.StashBoxEndpoint)
		if err != nil {
			return nil, err
		}

		client := r.newStashBoxClient(*b)

		switch {
		case input.SceneID != nil:
			var fps []models.Fingerprints
			fps, err = r.getScenesFingerprints(ctx, []int{sceneID})
			if err != nil {
				return nil, err
			}
			ret, err = client.FindSceneByFingerprints(ctx, fps[0])
		case input.Query != nil:
			ret, err = client.QueryScene(ctx, *input.Query)
		default:
			return nil, fmt.Errorf("%w: scene_id or query must be set", ErrInput)
		}

		if err != nil {
			return nil, err
		}

		// TODO - this should happen after any scene is scraped
		if err := r.matchScenesRelationships(ctx, ret, b.Endpoint); err != nil {
			return nil, err
		}
	default:
		return nil, fmt.Errorf("%w: scraper_id or stash_box_index must be set", ErrInput)
	}

	for i := range ret {
		slices.SortFunc(ret[i].Tags, models.ScrapedTagSortFunction)
	}

	if input.SceneID != nil {
		for _, scene := range ret {
			if scene == nil {
				continue
			}
			if err := r.saveScrapedSceneOnlineMedia(ctx, sceneID, scene.OnlineMedia); err != nil {
				return nil, err
			}
			break
		}
	}

	return ret, nil
}

func (r *queryResolver) ScrapeMultiScenes(ctx context.Context, source scraper.Source, input ScrapeMultiScenesInput) ([][]*models.ScrapedScene, error) {
	if source.ScraperID != nil {
		return nil, ErrNotImplemented
	} else if source.StashBoxIndex != nil || source.StashBoxEndpoint != nil {
		b, err := resolveStashBox(source.StashBoxIndex, source.StashBoxEndpoint)
		if err != nil {
			return nil, err
		}

		client := r.newStashBoxClient(*b)

		sceneIDs, err := stringslice.StringSliceToIntSlice(input.SceneIds)
		if err != nil {
			return nil, err
		}

		fps, err := r.getScenesFingerprints(ctx, sceneIDs)
		if err != nil {
			return nil, err
		}

		ret, err := client.FindScenesByFingerprints(ctx, fps)
		if err != nil {
			return nil, err
		}

		// match relationships - this mutates the existing scenes so we can
		// just flatten the slice and pass it in
		flat := sliceutil.Flatten(ret)

		if err := r.matchScenesRelationships(ctx, flat, b.Endpoint); err != nil {
			return nil, err
		}

		return ret, nil
	}

	return nil, errors.New("scraper_id or stash_box_index must be set")
}

func (r *queryResolver) getScenesFingerprints(ctx context.Context, ids []int) ([]models.Fingerprints, error) {
	fingerprints := make([]models.Fingerprints, len(ids))

	if err := r.withReadTxn(ctx, func(ctx context.Context) error {
		for i, sceneID := range ids {
			s, err := r.repository.Scene.Find(ctx, sceneID)
			if err != nil {
				return err
			}

			if s == nil {
				return fmt.Errorf("scene %d not found", sceneID)
			}

			for _, fp := range s.Fingerprints() {
				fingerprints[i] = append(fingerprints[i], match.Fingerprint{
					Algorithm: fp.Type,
					Hash:      fp.Value,
				})
			}
		}

		return nil
	}); err != nil {
		return nil, err
	}

	return fingerprints, nil
}
