package models

import (
	"encoding/json"
	"sync"
)

var scrapedSceneOnlineMedia sync.Map
var scrapedSceneOnlineMediaByKey sync.Map

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

	for _, key := range scrapedSceneOnlineMediaKeys(scene) {
		scrapedSceneOnlineMediaByKey.Store(key, copied)
	}
}

// GetScrapedSceneOnlineMedia returns raw online media scrape data previously
// attached to a scraped scene by SetScrapedSceneOnlineMedia.
func GetScrapedSceneOnlineMedia(scene *ScrapedScene) (json.RawMessage, bool) {
	if scene == nil {
		return nil, false
	}

	if value, ok := scrapedSceneOnlineMedia.Load(scene); ok {
		raw, ok := value.(json.RawMessage)
		return raw, ok
	}

	for _, key := range scrapedSceneOnlineMediaKeys(scene) {
		if value, ok := scrapedSceneOnlineMediaByKey.Load(key); ok {
			raw, ok := value.(json.RawMessage)
			return raw, ok
		}
	}

	return nil, false
}

// CopyScrapedSceneOnlineMedia copies transient online media data when scraped
// scenes are converted or copied through API helper functions.
func CopyScrapedSceneOnlineMedia(dst *ScrapedScene, src interface{}) {
	if dst == nil || src == nil {
		return
	}

	srcScene, ok := src.(*ScrapedScene)
	if !ok {
		return
	}

	raw, ok := GetScrapedSceneOnlineMedia(srcScene)
	if !ok {
		return
	}

	SetScrapedSceneOnlineMedia(dst, raw)
}

// AttachScrapedSceneOnlineMediaFromJSON attaches online_media from a raw script
// response to already-decoded ScrapedScene values. This covers scraper runners
// that decode into pointers and then copy/convert values before GraphQL resolves
// extension fields.
func AttachScrapedSceneOnlineMediaFromJSON(out interface{}, data []byte) error {
	if len(data) == 0 || out == nil {
		return nil
	}

	switch v := out.(type) {
	case **ScrapedScene:
		if v == nil || *v == nil {
			return nil
		}
		return attachSingleScrapedSceneOnlineMedia(*v, data)
	case *[]ScrapedScene:
		if v == nil {
			return nil
		}
		var rawItems []struct {
			OnlineMedia json.RawMessage `json:"online_media,omitempty"`
		}
		if err := json.Unmarshal(data, &rawItems); err != nil {
			return err
		}
		for i := range *v {
			if i < len(rawItems) {
				SetScrapedSceneOnlineMedia(&(*v)[i], rawItems[i].OnlineMedia)
			}
		}
	}

	return nil
}

func attachSingleScrapedSceneOnlineMedia(scene *ScrapedScene, data []byte) error {
	var raw struct {
		OnlineMedia json.RawMessage `json:"online_media,omitempty"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}

	SetScrapedSceneOnlineMedia(scene, raw.OnlineMedia)
	return nil
}

func scrapedSceneOnlineMediaKeys(scene *ScrapedScene) []string {
	if scene == nil {
		return nil
	}

	payload, err := json.Marshal(scene)
	if err != nil {
		return nil
	}

	var probe struct {
		URL          *string  `json:"url"`
		URLs         []string `json:"urls"`
		RemoteSiteID *string  `json:"remote_site_id"`
	}
	if err := json.Unmarshal(payload, &probe); err != nil {
		return nil
	}

	keys := make([]string, 0, len(probe.URLs)+2)
	for _, url := range probe.URLs {
		if url != "" {
			keys = append(keys, "url:"+url)
		}
	}
	if probe.URL != nil && *probe.URL != "" {
		keys = append(keys, "url:"+*probe.URL)
	}
	if probe.RemoteSiteID != nil && *probe.RemoteSiteID != "" {
		keys = append(keys, "remote_site_id:"+*probe.RemoteSiteID)
	}

	return keys
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
