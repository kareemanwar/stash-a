package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/stashapp/stash/pkg/models"
)

type scrapedSourcePayload struct {
	Title           string                  `json:"title"`
	URLs            []string                `json:"urls"`
	Details         *string                 `json:"details"`
	SourceType      models.SourceType       `json:"source_type"`
	ThumbnailURL    *string                 `json:"thumbnail_url"`
	RemoteSiteID    *string                 `json:"remote_site_id"`
	Parent          *scrapedSourcePayload   `json:"parent"`
	SceneCandidates []scrapedSceneCandidate `json:"scene_candidates"`
}

type scrapedSceneCandidate struct {
	Title           *string              `json:"title"`
	URLs            []string             `json:"urls"`
	Image           *string              `json:"image"`
	Date            *string              `json:"date"`
	RemoteSiteID    *string              `json:"remote_site_id"`
	Details         *string              `json:"details"`
	Duration        *int                 `json:"duration"`
	CandidateStatus *string              `json:"candidate_status"`
	CandidatePos    *int                 `json:"candidate_position"`
	Tags            []scrapedNamedObject  `json:"tags"`
	Performers      []scrapedNamedObject  `json:"performers"`
	Groups          []scrapedNamedObject  `json:"groups"`
	Galleries       []scrapedNamedObject  `json:"galleries"`
	OnlineMedia     json.RawMessage       `json:"online_media"`
}

type scrapedNamedObject struct {
	Name string `json:"name"`
}

func (r *mutationResolver) SourceSyncByURL(ctx context.Context, input models.SourceSyncByURLInput) (*models.SourceSyncResult, error) {
	url := strings.TrimSpace(input.URL)
	if url == "" {
		return nil, fmt.Errorf("source sync URL is required")
	}
	if !strings.Contains(strings.ToLower(url), "shrmha.com") {
		return nil, fmt.Errorf("no source-by-url scraper is registered for %q yet", url)
	}

	payload, err := runShrmhaSourceByURL(url)
	if err != nil {
		return nil, err
	}

	var source *models.Source
	var candidates []*models.SourceCandidateScene
	createdSource := false

	err = r.withTxn(ctx, func(ctx context.Context) error {
		parentID, err := r.ensureScrapedSourceParent(ctx, payload.Parent)
		if err != nil {
			return err
		}

		now := time.Now()
		source, createdSource, err = r.ensureScrapedSource(ctx, input.SourceID, payload, url, parentID, now)
		if err != nil {
			return err
		}

		ignored, err := r.sceneIgnoredURLMap(ctx, source.ID)
		if err != nil {
			return err
		}

		for index, scraped := range payload.SceneCandidates {
			candidateURL := firstCleanURL(scraped.URLs)
			if candidateURL == "" {
				continue
			}

			rawScrapedJSON, err := marshalString(scraped)
			if err != nil {
				return err
			}

			var rawOnlineMediaJSON *string
			if len(scraped.OnlineMedia) > 0 && string(scraped.OnlineMedia) != "null" {
				raw := string(scraped.OnlineMedia)
				rawOnlineMediaJSON = &raw
			}

			position := index
			if scraped.CandidatePos != nil {
				position = *scraped.CandidatePos
			}

			status := models.SourceCandidateStatusNew
			var targetSceneID *int
			if ignored[candidateURL] {
				status = models.SourceCandidateStatusIgnored
			} else {
				targetSceneID, err = r.repository.Source.FindSceneIDByURL(ctx, candidateURL)
				if err != nil {
					return err
				}
				if targetSceneID != nil {
					status = models.SourceCandidateStatusLinked
				}
			}

			candidate := &models.SourceCandidateScene{
				SourceID:           source.ID,
				ExternalID:         scraped.RemoteSiteID,
				URL:                candidateURL,
				Title:              scraped.Title,
				Date:               scraped.Date,
				Details:            scraped.Details,
				ThumbnailURL:       scraped.Image,
				DurationSeconds:    scraped.Duration,
				Position:           position,
				Status:             status,
				TargetSceneID:      targetSceneID,
				SourceSlug:         stringPtr("shrmha"),
				RawScrapedJSON:     rawScrapedJSON,
				RawOnlineMediaJSON: rawOnlineMediaJSON,
				LastScrapedAt:      &now,
				Tags:               scrapedRelations(scraped.Tags),
				Performers:         scrapedRelations(scraped.Performers),
				Groups:             scrapedRelations(scraped.Groups),
				Galleries:          scrapedRelations(scraped.Galleries),
			}
			if err := r.repository.Source.UpsertCandidateScene(ctx, candidate); err != nil {
				return err
			}
		}

		if err := r.repository.Source.MarkSynced(ctx, source.ID); err != nil {
			return err
		}

		source, err = r.repository.Source.Find(ctx, source.ID)
		if err != nil {
			return err
		}
		candidates, err = r.repository.Source.FindCandidateScenes(ctx, source.ID)
		return err
	})
	if err != nil {
		return nil, err
	}

	return &models.SourceSyncResult{
		Source:              source,
		CandidateScenes:     candidates,
		CandidateSceneCount: len(candidates),
		CreatedSource:       createdSource,
	}, nil
}

func runShrmhaSourceByURL(sourceURL string) (*scrapedSourcePayload, error) {
	python, err := exec.LookPath("python")
	if err != nil {
		python, err = exec.LookPath("python3")
		if err != nil {
			return nil, fmt.Errorf("python is required to run Shrmha source scraper: %w", err)
		}
	}

	scriptPath := filepath.Join(".local", "scrapers", "stash-a", "Shrmha", "ShrmhaSource.py")
	cmd := exec.Command(python, scriptPath, "source-by-url", "--url", sourceURL)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("Shrmha source scraper failed: %w: %s", err, strings.TrimSpace(stderr.String()))
	}

	var payload scrapedSourcePayload
	if err := json.Unmarshal(output, &payload); err != nil {
		return nil, fmt.Errorf("failed to parse Shrmha source scraper output: %w", err)
	}
	if strings.TrimSpace(payload.Title) == "" {
		return nil, fmt.Errorf("Shrmha source scraper returned an empty source title")
	}
	return &payload, nil
}

func (r *mutationResolver) ensureScrapedSourceParent(ctx context.Context, payload *scrapedSourcePayload) (*int, error) {
	if payload == nil {
		return nil, nil
	}

	urls := cleanSourceURLs(payload.URLs)
	if existing, err := r.findSourceByAnyURL(ctx, urls); err != nil || existing != nil {
		if existing == nil {
			return nil, err
		}
		return &existing.ID, nil
	}

	sourceType := payload.SourceType
	if sourceType == "" {
		sourceType = models.SourceTypeSite
	}
	parent := &models.Source{
		Title:        strings.TrimSpace(payload.Title),
		Details:      payload.Details,
		Type:         sourceType,
		ThumbnailURL: payload.ThumbnailURL,
		URLs:         urls,
	}
	if parent.Title == "" {
		parent.Title = "Source"
	}
	if err := r.repository.Source.Create(ctx, parent); err != nil {
		return nil, err
	}
	return &parent.ID, nil
}

func (r *mutationResolver) ensureScrapedSource(ctx context.Context, sourceIDInput *string, payload *scrapedSourcePayload, requestedURL string, parentID *int, syncedAt time.Time) (*models.Source, bool, error) {
	urls := cleanSourceURLs(append([]string{requestedURL}, payload.URLs...))
	sourceType := payload.SourceType
	if sourceType == "" {
		sourceType = models.SourceTypeSearch
	}

	var source *models.Source
	created := false
	if sourceIDInput != nil && strings.TrimSpace(*sourceIDInput) != "" {
		sid, err := sourceID(*sourceIDInput)
		if err != nil {
			return nil, false, err
		}
		found, err := r.repository.Source.Find(ctx, sid)
		if err != nil {
			return nil, false, err
		}
		if found == nil {
			return nil, false, fmt.Errorf("source %d not found", sid)
		}
		source = found
	} else {
		found, err := r.findSourceByAnyURL(ctx, urls)
		if err != nil {
			return nil, false, err
		}
		source = found
	}

	if source == nil {
		source = &models.Source{
			Title:        strings.TrimSpace(payload.Title),
			Details:      payload.Details,
			Type:         sourceType,
			ParentID:     parentID,
			ThumbnailURL: payload.ThumbnailURL,
			LastSyncedAt: &syncedAt,
			URLs:         urls,
		}
		if source.Title == "" {
			source.Title = requestedURL
		}
		if err := r.repository.Source.Create(ctx, source); err != nil {
			return nil, false, err
		}
		return source, true, nil
	}

	if strings.TrimSpace(payload.Title) != "" {
		source.Title = strings.TrimSpace(payload.Title)
	}
	source.Details = payload.Details
	source.Type = sourceType
	source.ParentID = parentID
	source.ThumbnailURL = payload.ThumbnailURL
	source.LastSyncedAt = &syncedAt
	source.URLs = urls
	if err := r.repository.Source.Update(ctx, source); err != nil {
		return nil, false, err
	}
	return source, created, nil
}

func (r *mutationResolver) findSourceByAnyURL(ctx context.Context, urls []string) (*models.Source, error) {
	for _, url := range urls {
		trimmed := strings.TrimSpace(url)
		if trimmed == "" {
			continue
		}
		source, err := r.repository.Source.FindByURL(ctx, trimmed)
		if err != nil || source != nil {
			return source, err
		}
	}
	return nil, nil
}

func (r *mutationResolver) sceneIgnoredURLMap(ctx context.Context, sourceID int) (map[string]bool, error) {
	ignoredItems, err := r.repository.Source.FindIgnoredItems(ctx, sourceID)
	if err != nil {
		return nil, err
	}
	ret := map[string]bool{}
	for _, item := range ignoredItems {
		if item == nil || item.ContentType != models.SourceIgnoredContentTypeScene {
			continue
		}
		ret[item.URL] = true
	}
	return ret, nil
}

func firstCleanURL(urls []string) string {
	for _, url := range urls {
		trimmed := strings.TrimSpace(url)
		if trimmed != "" {
			return trimmed
		}
	}
	return ""
}

func marshalString(v interface{}) (*string, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	ret := string(b)
	return &ret, nil
}

func stringPtr(v string) *string {
	return &v
}

func scrapedRelations(objects []scrapedNamedObject) []*models.SourceCandidateRelation {
	ret := []*models.SourceCandidateRelation{}
	seen := map[string]struct{}{}
	for i, obj := range objects {
		name := strings.TrimSpace(obj.Name)
		if name == "" {
			continue
		}
		if _, ok := seen[name]; ok {
			continue
		}
		seen[name] = struct{}{}
		ret = append(ret, &models.SourceCandidateRelation{Name: name, Position: i})
	}
	return ret
}
