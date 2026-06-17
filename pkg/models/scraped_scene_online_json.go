package models

import (
	"encoding/json"
	"sync"
)

var scrapedSceneOnlineMedia sync.Map

// SetScrapedSceneOnlineMedia attaches raw online media scrape data to a scraped scene.
// This is used only as transient scrape transport so script scrapers can return
// provider playback metadata without storing it in custom_fields or native Scene
// metadata before the user creates/imports the scene.
func SetScrapedSceneOnlineMedia(scene *ScrapedScene, raw json.RawMessage) {
	if scene == nil || len(raw) == 0 || string(raw) == "null" {
		return
	}

	copied := make(json.RawMessage, len(raw))
	copy(copied, raw)
	scrapedSceneOnlineMedia.Store(scene, copied)
}

// GetScrapedSceneOnlineMedia returns raw online media scrape data previously
// attached to a scraped scene by SetScrapedSceneOnlineMedia.
func GetScrapedSceneOnlineMedia(scene *ScrapedScene) (json.RawMessage, bool) {
	if scene == nil {
		return nil, false
	}

	value, ok := scrapedSceneOnlineMedia.Load(scene)
	if !ok {
		return nil, false
	}

	raw, ok := value.(json.RawMessage)
	return raw, ok
}

// UnmarshalJSON preserves the upstream ScrapedScene shape while accepting the
// Stash-a online_media extension returned by script scrapers. Unknown fields are
// intentionally ignored here to match the scraper runner's lenient fallback.
func (s *ScrapedScene) UnmarshalJSON(data []byte) error {
	type scrapedSceneAlias ScrapedScene
	aux := struct {
		*scrapedSceneAlias
		OnlineMedia json.RawMessage `json:"online_media,omitempty"`
	}{
		scrapedSceneAlias: (*scrapedSceneAlias)(s),
	}

	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}

	SetScrapedSceneOnlineMedia(s, aux.OnlineMedia)
	return nil
}
