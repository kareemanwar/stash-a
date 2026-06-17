import React, { useMemo, useState } from "react";
import { gql, useMutation, useQuery } from "@apollo/client";
import { Alert, Badge, Button, Card, Col, Form, Row, Tab, Tabs } from "react-bootstrap";
import { Helmet } from "react-helmet";

const FIND_SOURCES = gql`
  query FindSourcesForReview {
    findSources {
      count
      sources {
        id
        title
        urls
        type
        thumbnail_url
        last_synced_at
        candidate_scene_count
        ignored_count
      }
    }
  }
`;

const FIND_SOURCE_CANDIDATE_SCENES = gql`
  query FindSourceCandidateScenesForReview($source_id: ID!) {
    findSourceCandidateScenes(source_id: $source_id) {
      id
      source_id
      external_id
      url
      title
      date
      details
      thumbnail_url
      position
      status
      target_scene_id
      tags {
        id
        name
        position
      }
    }
  }
`;

const SYNC_SOURCE_BY_URL = gql`
  mutation SyncSourceByURLForReview($input: SourceSyncByURLInput!) {
    sourceSyncByURL(input: $input) {
      created_source
      candidate_scene_count
      source {
        id
        title
        urls
        type
        thumbnail_url
        last_synced_at
        candidate_scene_count
        ignored_count
      }
      candidate_scenes {
        id
        source_id
        external_id
        url
        title
        date
        details
        thumbnail_url
        position
        status
        target_scene_id
        tags {
          id
          name
          position
        }
      }
    }
  }
`;

const IGNORE_SOURCE_ITEM = gql`
  mutation IgnoreSourceCandidate($input: SourceIgnoreItemInput!) {
    sourceIgnoreItem(input: $input) {
      id
    }
  }
`;

type SourceSummary = {
  id: string;
  title: string;
  urls: string[];
  type: string;
  thumbnail_url?: string | null;
  last_synced_at?: string | null;
  candidate_scene_count: number;
  ignored_count: number;
};

type CandidateRelation = {
  id?: string | null;
  name: string;
  position: number;
};

type CandidateScene = {
  id: string;
  source_id: string;
  external_id?: string | null;
  url: string;
  title?: string | null;
  date?: string | null;
  details?: string | null;
  thumbnail_url?: string | null;
  position: number;
  status: "NEW" | "LINKED" | "PROMOTED" | "IGNORED" | "STALE" | "ERROR";
  target_scene_id?: string | null;
  tags: CandidateRelation[];
};

function statusVariant(status: CandidateScene["status"]) {
  switch (status) {
    case "LINKED":
    case "PROMOTED":
      return "success";
    case "IGNORED":
    case "STALE":
      return "secondary";
    case "ERROR":
      return "danger";
    case "NEW":
    default:
      return "warning";
  }
}

function borderColor(status: CandidateScene["status"]) {
  switch (status) {
    case "LINKED":
    case "PROMOTED":
      return "#28a745";
    case "IGNORED":
    case "STALE":
      return "#6c757d";
    case "ERROR":
      return "#dc3545";
    case "NEW":
    default:
      return "#ffc107";
  }
}

const CandidateSceneCard: React.FC<{
  candidate: CandidateScene;
  onIgnore: (candidate: CandidateScene) => void;
}> = ({ candidate, onIgnore }) => {
  return (
    <Col xs={12} sm={6} md={4} xl={3} className="mb-3">
      <Card
        className="h-100 source-candidate-scene-card"
        style={{ border: `2px solid ${borderColor(candidate.status)}` }}
      >
        {candidate.thumbnail_url && (
          <a href={candidate.url} target="_blank" rel="noreferrer">
            <Card.Img variant="top" src={candidate.thumbnail_url} />
          </a>
        )}
        <Card.Body className="d-flex flex-column">
          <div className="mb-2 d-flex justify-content-between align-items-start">
            <Badge variant={statusVariant(candidate.status)}>{candidate.status}</Badge>
            {candidate.target_scene_id && (
              <Badge variant="success">Scene #{candidate.target_scene_id}</Badge>
            )}
          </div>
          <Card.Title className="h6">{candidate.title || candidate.url}</Card.Title>
          {candidate.date && <Card.Subtitle className="mb-2 text-muted">{candidate.date}</Card.Subtitle>}
          {candidate.tags.length > 0 && (
            <div className="mb-2">
              {candidate.tags.map((tag) => (
                <Badge key={`${candidate.id}-${tag.position}-${tag.name}`} variant="dark" className="mr-1 mb-1">
                  {tag.name}
                </Badge>
              ))}
            </div>
          )}
          <div className="mt-auto d-flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline-primary"
              href={candidate.url}
              target="_blank"
              rel="noreferrer"
            >
              Open
            </Button>
            {candidate.status !== "IGNORED" && (
              <Button size="sm" variant="outline-secondary" onClick={() => onIgnore(candidate)}>
                Ignore
              </Button>
            )}
          </div>
        </Card.Body>
      </Card>
    </Col>
  );
};

const Sources: React.FC = () => {
  const [syncURL, setSyncURL] = useState(
    "https://shrmha.com/?paged=2&s=%D8%A7%D9%86%D8%AC%D9%8A+%D8%AE%D9%88%D8%B1%D9%8A"
  );
  const [selectedSourceID, setSelectedSourceID] = useState<string | undefined>();
  const [error, setError] = useState<string | undefined>();

  const sourcesQuery = useQuery(FIND_SOURCES);
  const candidateQuery = useQuery(FIND_SOURCE_CANDIDATE_SCENES, {
    variables: { source_id: selectedSourceID || "" },
    skip: !selectedSourceID,
    fetchPolicy: "cache-and-network",
  });

  const [syncSourceByURL, syncState] = useMutation(SYNC_SOURCE_BY_URL, {
    onCompleted: (data) => {
      const source = data?.sourceSyncByURL?.source;
      if (source?.id) {
        setSelectedSourceID(source.id);
      }
      sourcesQuery.refetch();
      candidateQuery.refetch?.();
      setError(undefined);
    },
    onError: (err) => setError(err.message),
  });

  const [ignoreSourceItem] = useMutation(IGNORE_SOURCE_ITEM, {
    onCompleted: () => candidateQuery.refetch?.(),
    onError: (err) => setError(err.message),
  });

  const sources: SourceSummary[] = sourcesQuery.data?.findSources?.sources ?? [];
  const candidates: CandidateScene[] =
    candidateQuery.data?.findSourceCandidateScenes ??
    syncState.data?.sourceSyncByURL?.candidate_scenes ??
    [];

  const selectedSource = useMemo(
    () => sources.find((source) => source.id === selectedSourceID),
    [sources, selectedSourceID]
  );

  async function handleSync() {
    if (!syncURL.trim()) return;
    await syncSourceByURL({ variables: { input: { url: syncURL.trim(), source_id: selectedSourceID } } });
  }

  async function handleIgnore(candidate: CandidateScene) {
    await ignoreSourceItem({
      variables: {
        input: {
          source_id: candidate.source_id,
          content_type: "SCENE",
          external_id: candidate.external_id,
          url: candidate.url,
          title: candidate.title,
          thumbnail_url: candidate.thumbnail_url,
        },
      },
    });
  }

  return (
    <div className="sources-page">
      <Helmet title="Sources" />
      <h2>Sources</h2>
      <Card className="mb-3">
        <Card.Body>
          <Form.Group>
            <Form.Label>Source URL</Form.Label>
            <Form.Control
              value={syncURL}
              onChange={(event) => setSyncURL(event.currentTarget.value)}
              placeholder="Paste a source URL"
            />
          </Form.Group>
          <Button disabled={syncState.loading || !syncURL.trim()} onClick={handleSync}>
            {syncState.loading ? "Syncing..." : "Sync"}
          </Button>
        </Card.Body>
      </Card>

      {error && <Alert variant="danger">{error}</Alert>}

      <Row>
        <Col lg={3} className="mb-3">
          <h4>Sources</h4>
          {sourcesQuery.loading && <div>Loading sources...</div>}
          {sources.map((source) => (
            <Card
              key={source.id}
              className="mb-2"
              onClick={() => setSelectedSourceID(source.id)}
              style={{ cursor: "pointer", borderColor: selectedSourceID === source.id ? "#007bff" : undefined }}
            >
              <Card.Body>
                <div className="d-flex justify-content-between align-items-start">
                  <strong>{source.title}</strong>
                  <Badge variant="info">{source.type}</Badge>
                </div>
                <div className="small text-muted text-truncate">{source.urls?.[0]}</div>
                <div className="mt-2 small">
                  <Badge variant="warning" className="mr-1">{source.candidate_scene_count} videos</Badge>
                  <Badge variant="secondary">{source.ignored_count} ignored</Badge>
                </div>
              </Card.Body>
            </Card>
          ))}
        </Col>

        <Col lg={9}>
          {selectedSource ? (
            <>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h3>{selectedSource.title}</h3>
                  <div className="text-muted small">{selectedSource.urls?.[0]}</div>
                </div>
                <Button variant="outline-primary" onClick={handleSync} disabled={syncState.loading}>
                  Sync selected
                </Button>
              </div>
              <Tabs defaultActiveKey="videos" id="source-detail-tabs">
                <Tab eventKey="videos" title={`Videos (${candidates.length})`}>
                  <div className="pt-3">
                    {candidateQuery.loading && <div>Loading candidates...</div>}
                    <Row>
                      {candidates.map((candidate) => (
                        <CandidateSceneCard
                          key={candidate.id}
                          candidate={candidate}
                          onIgnore={handleIgnore}
                        />
                      ))}
                    </Row>
                  </div>
                </Tab>
                <Tab eventKey="images" title="Images">
                  <div className="pt-3 text-muted">Image candidates are reserved for the next implementation pass.</div>
                </Tab>
                <Tab eventKey="galleries" title="Galleries">
                  <div className="pt-3 text-muted">Gallery candidates are reserved for the next implementation pass.</div>
                </Tab>
                <Tab eventKey="sources" title="Sources">
                  <div className="pt-3 text-muted">Child source candidates are reserved for the next implementation pass.</div>
                </Tab>
                <Tab eventKey="ignored" title="Ignored">
                  <div className="pt-3 text-muted">Ignored media are saved by source and will get a dedicated list next.</div>
                </Tab>
              </Tabs>
            </>
          ) : (
            <Alert variant="info">Sync a URL or select a source to review candidate media.</Alert>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default Sources;
