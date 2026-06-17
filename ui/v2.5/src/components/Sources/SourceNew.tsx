import React, { useState } from "react";
import { gql, useMutation, useQuery } from "@apollo/client";
import { Alert, Button, Card, Col, Form, Row } from "react-bootstrap";
import { Helmet } from "react-helmet";
import { useHistory } from "react-router-dom";

const FIND_SOURCES = gql`
  query FindSourcesForCreate {
    findSources {
      sources {
        id
        title
      }
    }
  }
`;

const CREATE_SOURCE = gql`
  mutation CreateSourceFromPage($input: SourceCreateInput!) {
    sourceCreate(input: $input) {
      id
      title
      urls
    }
  }
`;

const SYNC_SOURCE_BY_URL = gql`
  mutation SyncSourceFromCreatePage($input: SourceSyncByURLInput!) {
    sourceSyncByURL(input: $input) {
      source {
        id
      }
    }
  }
`;

const SOURCE_TYPES = [
  "SITE",
  "SITE_SECTION",
  "SEARCH",
  "CATEGORY",
  "ACCOUNT",
  "CHANNEL",
  "PROFILE",
  "COLLECTION",
  "OTHER",
];

const SourceNew: React.FC = () => {
  const history = useHistory();
  const [title, setTitle] = useState("");
  const [url, setURL] = useState("");
  const [type, setType] = useState("SEARCH");
  const [parentID, setParentID] = useState("");
  const [thumbnailURL, setThumbnailURL] = useState("");
  const [details, setDetails] = useState("");
  const [syncAfterCreate, setSyncAfterCreate] = useState(true);
  const [error, setError] = useState<string | undefined>();

  const sourcesQuery = useQuery(FIND_SOURCES);
  const [createSource, createState] = useMutation(CREATE_SOURCE, {
    onError: (err) => setError(err.message),
  });
  const [syncSource, syncState] = useMutation(SYNC_SOURCE_BY_URL, {
    onError: (err) => setError(err.message),
  });

  const sources = sourcesQuery.data?.findSources?.sources ?? [];
  const canCreate = title.trim().length > 0 || url.trim().length > 0;
  const loading = createState.loading || syncState.loading;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canCreate) return;

    const trimmedURL = url.trim();
    const input = {
      title: title.trim() || trimmedURL,
      urls: trimmedURL ? [trimmedURL] : [],
      type,
      parent_id: parentID || null,
      thumbnail_url: thumbnailURL.trim() || null,
      details: details.trim() || null,
    };

    const result = await createSource({ variables: { input } });
    const source = result.data?.sourceCreate;

    if (syncAfterCreate && trimmedURL && source?.id) {
      await syncSource({ variables: { input: { url: trimmedURL, source_id: source.id } } });
    }

    history.push("/sources");
  }

  return (
    <div className="source-create-page">
      <Helmet title="New Source" />
      <h2>New Source</h2>
      <Card>
        <Card.Body>
          {error && <Alert variant="danger">{error}</Alert>}
          <Form onSubmit={onSubmit}>
            <Row>
              <Col md={8}>
                <Form.Group>
                  <Form.Label>Title</Form.Label>
                  <Form.Control
                    value={title}
                    onChange={(event) => setTitle(event.currentTarget.value)}
                    placeholder="Leave empty to use the scraped source title"
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group>
                  <Form.Label>Type</Form.Label>
                  <Form.Control
                    as="select"
                    value={type}
                    onChange={(event) => setType(event.currentTarget.value)}
                  >
                    {SOURCE_TYPES.map((sourceType) => (
                      <option key={sourceType} value={sourceType}>
                        {sourceType}
                      </option>
                    ))}
                  </Form.Control>
                </Form.Group>
              </Col>
            </Row>

            <Form.Group>
              <Form.Label>Source URL</Form.Label>
              <Form.Control
                value={url}
                onChange={(event) => setURL(event.currentTarget.value)}
                placeholder="https://example.com/search-or-source"
              />
              <Form.Text className="text-muted">
                Matching source scrapers may crawl pagination and create candidate media.
              </Form.Text>
            </Form.Group>

            <Row>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Parent source</Form.Label>
                  <Form.Control
                    as="select"
                    value={parentID}
                    onChange={(event) => setParentID(event.currentTarget.value)}
                  >
                    <option value="">None</option>
                    {sources.map((source: { id: string; title: string }) => (
                      <option key={source.id} value={source.id}>
                        {source.title}
                      </option>
                    ))}
                  </Form.Control>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Thumbnail URL</Form.Label>
                  <Form.Control
                    value={thumbnailURL}
                    onChange={(event) => setThumbnailURL(event.currentTarget.value)}
                    placeholder="Optional remote thumbnail"
                  />
                </Form.Group>
              </Col>
            </Row>

            <Form.Group>
              <Form.Label>Details</Form.Label>
              <Form.Control
                as="textarea"
                rows={4}
                value={details}
                onChange={(event) => setDetails(event.currentTarget.value)}
              />
            </Form.Group>

            <Form.Check
              id="source-sync-after-create-page"
              checked={syncAfterCreate}
              onChange={(event) => setSyncAfterCreate(event.currentTarget.checked)}
              label="Sync this source after create"
              className="mb-3"
            />

            <div className="d-flex justify-content-end">
              <Button
                variant="secondary"
                className="mr-2"
                onClick={() => history.push("/sources")}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!canCreate || loading}>
                {loading ? "Creating..." : "Create"}
              </Button>
            </div>
          </Form>
        </Card.Body>
      </Card>
    </div>
  );
};

export default SourceNew;
