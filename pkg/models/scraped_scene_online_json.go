package models

import "encoding/json"

// SetScrapedSceneOnlineMedia attaches online media scrape data to a scraped
// scene. This is transient scrape transport only; persistent online playback is
// stored through SceneOnlineMedia after the user applies/saves the scrape result.
func SetScrapedSceneOnlineMedia(scene *ScrapedScene, raw json.RawMessage) {
	if scene == nil || len(raw) == 0 || string(raw) == "null" {
		return
	}

	var media ScrapedSceneOnlineMedia
	if err := json.Unmarshal(raw, &media); err != nil {
		return
	}
	if media.Streams == nil {
		media.Streams = []*ScrapedSceneOnlineStream{}
	}

	scene.OnlineMedia = &media
}

// GetScrapedSceneOnlineMedia returns online media scrape data attached to a
// scraped scene.
func GetScrapedSceneOnlineMedia(scene *ScrapedScene) (json.RawMessage, bool) {
	if scene == nil || scene.OnlineMedia == nil {
		return nil, false
	}

	raw, err := json.Marshal(scene.OnlineMedia)
	if err != nil {
		return nil, false
	}

	return raw, true
}

// CopyScrapedSceneOnlineMedia copies transient online media data when scraped
// scenes are converted or copied through API helper functions.
func CopyScrapedSceneOnlineMedia(dst *ScrapedScene, src interface{}) {
	if dst == nil || src == nil {
		return
	}

	srcScene, ok := src.(*ScrapedScene)
	if !ok || srcScene.OnlineMedia == nil {
		return
	}

	raw, ok := GetScrapedSceneOnlineMedia(srcScene)
	if !ok {
		return
	}

	SetScrapedSceneOnlineMedia(dst, raw)
}

// AttachScrapedSceneOnlineMediaFromJSON attaches online_media from a raw script
// response to already-decoded ScrapedScene values. This preserves compatibility
// with scraper runners that decode and then copy/convert values.
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

// UnmarshalJSON preserves the upstream ScrapedScene shape while accepting the
// Stash-a online_media extension returned by script scrapers.
func (s *ScrapedScene) UnmarshalJSON(data []byte) error {
	type scrapedSceneAlias ScrapedScene

	if err := json.Unmarshal(data, (*scrapedSceneAlias)(s)); err != nil {
		return err
	}
	if s.OnlineMedia != nil && s.OnlineMedia.Streams == nil {
		s.OnlineMedia.Streams = []*ScrapedSceneOnlineStream{}
	}

	return nil
}
