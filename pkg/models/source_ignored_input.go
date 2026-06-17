package models

type SourceIgnoreItemInput struct {
	SourceID     string                   `json:"source_id"`
	ContentType  SourceIgnoredContentType `json:"content_type"`
	ExternalID   *string                  `json:"external_id"`
	URL          string                   `json:"url"`
	Title        *string                  `json:"title"`
	ThumbnailURL *string                  `json:"thumbnail_url"`
	Reason       *string                  `json:"reason"`
}

type SourceUnignoreItemInput struct {
	SourceID    string                   `json:"source_id"`
	ContentType SourceIgnoredContentType `json:"content_type"`
	URL         string                   `json:"url"`
}
