import React, { useEffect, useMemo, useState } from "react";
import { gql, useMutation, useQuery } from "@apollo/client";
import {
  Alert,
  Badge,
  Button,
  ButtonGroup,
  Card,
  Col,
  Form,
  Modal,
  Row,
  Tab,
  Tabs,
} from "react-bootstrap";
import { Helmet } from "react-helmet";
import { ListOperations } from "../List/ListOperationButtons";
import { GridCard } from "../Shared/GridCard/GridCard";

const FIND_SOURCES = gql`
  query FindSourcesForReview {
    findSources {
      count
      sources {
        id
        title
        urls
        details
        type
        parent_id
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
      duration_seconds
      position
      status
      target_scene_id
      tags {
        id
        name
        position
      }
      performers {
        id
        name
        position
      }
      groups {
        id
        name
        position
      }
      galleries {
        id
        name
        position
      }
    }
  }
`;

const FIND_SOURCE_IGNORED_ITEMS = gql`
  query FindSourceIgnoredItemsForReview($source_id: ID!) {
    findSourceIgnoredItems(source_id: $source_id) {
      id
      source_id
      content_type
      external_id
      url
      title
      thumbnail_url
      reason
      ignored_at
    }
  }
`;

const CREATE_SOURCE = gql`
  mutation CreateSourceForReview($input: SourceCreateInput!) {
    sourceCreate(input: $input) {
      id
      title
      urls
      details
      type
      parent_id
      thumbnail_url
      last_synced_at
      candidate_scene_count
      ignored_count
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
        details
        type
        parent_id
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
        duration_seconds
        position
        status
        target_scene_id
        tags {
          id
          name
          position
        }
        performers {
          id
          name
          position
        }
        groups {
          id
          name
          position
        }
        galleries {
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

const UNIGNORE_SOURCE_ITEM = gql`
  mutation UnignoreSourceCandidate($input: SourceUnignoreItemInput!) {
    sourceUnignoreItem(input: $input)
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

type SourceSummary = {
  id: string;
  title: string;
  urls: string[];
  details?: string | null;
  type: string;
  parent_id?: string | null;
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
  duration_seconds?: number | null;
  position: number;
  status: "NEW" | "LINKED" | "PROMOTED" | "IGNORED" | "STALE" | "ERROR";
  target_scene_id?: string | null;
  tags: CandidateRelation[];
  performers: CandidateRelation[];
  groups: CandidateRelation[];
  galleries: CandidateRelation[];
};

type IgnoredItem = {
  id: string;
  source_id: string;
  content_type: string;
  external_id?: string | null;
  url: string;
  title?: string | null;
  thumbnail_url?: string | null;
  reason?: string | null;
  ignored_at: string;
};

type SourceFormState = {
  title: string;
  url: string;
  type: string;
  parent_id: string;
  thumbnail_url: string;
  details: string;
  syncAfterCreate: boolean;
};

const EMPTY_SOURCE_FORM: SourceFormState = {
  title: "",
  url: "",
  type: "SEARCH",
  parent_id: "",
  thumbnail_url: "",
  details: "",
  syncAfterCreate: true,
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

function formatDate(value?: string | null) {
  if (!value) return undefined;
  return value.length > 10 ? value.slice(0, 10) : value;
}

function relationBadges(relations: CandidateRelation[], variant = "dark") {
  if (relations.length === 0) return null;

  return (
    <div className="source-candidate-relations">
      {relations.map((relation) => (
        <Badge
          key={`${relation.position}-${relation.name}`}
          variant={variant}
          className="mr-1 mb-1"
        >
          {relation.name}
        </Badge>
      ))}
    </div>
  );
}

const SourceCreateDialog: React.FC<{
  show: boolean;
  sources: SourceSummary[];
  loading: boolean;
  onHide: () => void;
  onCreate: (form: SourceFormState) => Promise<void>;
}> = ({ show, sources, loading, onHide, onCreate }) => {
  const [form, setForm] = useState<SourceFormState>(EMPTY_SOURCE_FORM);

  useEffect(() => {
    if (show) {
      setForm(EMPTY_SOURCE_FORM);
    }
  }, [show]);

  function setFormField(field: keyof SourceFormState, value: string | boolean) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  const canCreate = form.title.trim().length > 0 || form.url.trim().length > 0;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canCreate) return;
    await onCreate(form);
  }

  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Form onSubmit={handleSubmit}>
        <Modal.Header closeButton>
          <Modal.Title>New Source</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Row>
            <Col md={8}>
              <Form.Group>
                <Form.Label>Title</Form.Label>
                <Form.Control
                  value={form.title}
                  onChange={(event) => setFormField("title", event.currentTarget.value)}
                  placeholder="Leave empty to use the scraped source title"
                />
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Type</Form.Label>
                <Form.Control
                  as="select"
                  value={form.type}
                  onChange={(event) => setFormField("type", event.currentTarget.value)}
                >
                  {SOURCE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </Form.Control>
              </Form.Group>
            </Col>
          </Row>

          <Form.Group>
            <Form.Label>Source URL</Form.Label>
            <Form.Control
              value={form.url}
              onChange={(event) => setFormField("url", event.currentTarget.value)}
              placeholder="https://shrmha.com/?s=... or https://shrmha.com/"
            />
            <Form.Text className="text-muted">
              The source URL is synced through the matching scraper and may crawl pagination.
            </Form.Text>
          </Form.Group>

          <Row>
            <Col md={6}>
              <Form.Group>
                <Form.Label>Parent source</Form.Label>
                <Form.Control
                  as="select"
                  value={form.parent_id}
                  onChange={(event) => setFormField("parent_id", event.currentTarget.value)}
                >
                  <option value="">None</option>
                  {sources.map((source) => (
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
                  value={form.thumbnail_url}
                  onChange={(event) => setFormField("thumbnail_url", event.currentTarget.value)}
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
              value={form.details}
              onChange={(event) => setFormField("details", event.currentTarget.value)}
            />
          </Form.Group>

          <Form.Check
            id="source-sync-after-create"
            checked={form.syncAfterCreate}
            onChange={(event) => setFormField("syncAfterCreate", event.currentTarget.checked)}
            label="Sync this source after create"
          />
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={onHide} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" disabled={!canCreate || loading}>
            {loading ? "Creating..." : "Create"}
          </Button>
        </Modal.Footer>
      </Form>
    </Modal>
  );
};

const CandidateSceneCard: React.FC<{
  candidate: CandidateScene;
  selected: boolean;
  onSelectedChanged: (candidate: CandidateScene, selected: boolean, shiftKey: boolean) => void;
  onIgnore: (candidate: CandidateScene) => void;
}> = ({ candidate, selected, onSelectedChanged, onIgnore }) => {
  const relationContent = (
    <>
      {relationBadges(candidate.performers, "primary")}
      {relationBadges(candidate.tags, "dark")}
      {relationBadges(candidate.groups, "info")}
      {relationBadges(candidate.galleries, "secondary")}
    </>
  );

  const image = (
    <div className="source-candidate-preview">
      {candidate.thumbnail_url ? (
        <img src={candidate.thumbnail_url} alt="" loading="lazy" />
      ) : (
        <div className="source-candidate-preview-placeholder">No thumbnail</div>
      )}
      <div className="source-candidate-status-overlay">
        <Badge variant={statusVariant(candidate.status)}>{candidate.status}</Badge>
      </div>
    </div>
  );

  const details = (
    <div className="scene-card__details source-candidate-details">
      <div className="d-flex align-items-center flex-wrap">
        {formatDate(candidate.date) && (
          <span className="scene-card__date mr-2">{formatDate(candidate.date)}</span>
        )}
        {candidate.target_scene_id && (
          <Badge variant="success">Scene #{candidate.target_scene_id}</Badge>
        )}
      </div>
      <span className="file-path extra-scene-info text-truncate d-block">
        {candidate.url}
      </span>
      {relationContent}
    </div>
  );

  const popovers = (
    <div className="source-candidate-actions">
      <ButtonGroup size="sm">
        <Button
          variant="outline-primary"
          href={candidate.url}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => event.stopPropagation()}
        >
          Open
        </Button>
        {candidate.status !== "IGNORED" && (
          <Button
            variant="outline-secondary"
            onClick={(event) => {
              event.stopPropagation();
              onIgnore(candidate);
            }}
          >
            Ignore
          </Button>
        )}
      </ButtonGroup>
    </div>
  );

  return (
    <GridCard
      className={`scene-card source-candidate-scene-card source-candidate-scene-card--${candidate.status.toLowerCase()}`}
      url={`/sources?source=${candidate.source_id}&candidate=${candidate.id}`}
      title={candidate.title || candidate.url}
      linkClassName="scene-card-link"
      thumbnailSectionClassName="video-section"
      image={image}
      details={details}
      popovers={popovers}
      selected={selected}
      selecting
      onSelectedChanged={(isSelected, shiftKey) =>
        onSelectedChanged(candidate, isSelected, shiftKey)
      }
    />
  );
};

const Sources: React.FC = () => {
  const [selectedSourceID, setSelectedSourceID] = useState<string | undefined>();
  const [selectedCandidateIDs, setSelectedCandidateIDs] = useState<Set<string>>(new Set());
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const sourcesQuery = useQuery(FIND_SOURCES);
  const candidateQuery = useQuery(FIND_SOURCE_CANDIDATE_SCENES, {
    variables: { source_id: selectedSourceID || "" },
    skip: !selectedSourceID,
    fetchPolicy: "cache-and-network",
  });
  const ignoredQuery = useQuery(FIND_SOURCE_IGNORED_ITEMS, {
    variables: { source_id: selectedSourceID || "" },
    skip: !selectedSourceID,
    fetchPolicy: "cache-and-network",
  });

  const [createSource, createState] = useMutation(CREATE_SOURCE, {
    onError: (err) => setError(err.message),
  });

  const [syncSourceByURL, syncState] = useMutation(SYNC_SOURCE_BY_URL, {
    onCompleted: (data) => {
      const source = data?.sourceSyncByURL?.source;
      if (source?.id) {
        setSelectedSourceID(source.id);
      }
      sourcesQuery.refetch();
      candidateQuery.refetch?.();
      ignoredQuery.refetch?.();
      setSelectedCandidateIDs(new Set());
      setError(undefined);
    },
    onError: (err) => setError(err.message),
  });

  const [ignoreSourceItem] = useMutation(IGNORE_SOURCE_ITEM, {
    onCompleted: () => {
      candidateQuery.refetch?.();
      ignoredQuery.refetch?.();
    },
    onError: (err) => setError(err.message),
  });

  const [unignoreSourceItem] = useMutation(UNIGNORE_SOURCE_ITEM, {
    onCompleted: () => {
      candidateQuery.refetch?.();
      ignoredQuery.refetch?.();
      sourcesQuery.refetch();
    },
    onError: (err) => setError(err.message),
  });

  const sources: SourceSummary[] = sourcesQuery.data?.findSources?.sources ?? [];
  const candidates: CandidateScene[] =
    candidateQuery.data?.findSourceCandidateScenes ??
    syncState.data?.sourceSyncByURL?.candidate_scenes ??
    [];
  const ignoredItems: IgnoredItem[] = ignoredQuery.data?.findSourceIgnoredItems ?? [];

  const selectedSource = useMemo(
    () => sources.find((source) => source.id === selectedSourceID),
    [sources, selectedSourceID]
  );

  useEffect(() => {
    setSelectedCandidateIDs(new Set());
  }, [selectedSourceID]);

  async function handleCreateSource(form: SourceFormState) {
    const url = form.url.trim();
    const title = form.title.trim() || url;
    if (!title) return;

    const input = {
      title,
      urls: url ? [url] : [],
      type: form.type,
      parent_id: form.parent_id || null,
      thumbnail_url: form.thumbnail_url.trim() || null,
      details: form.details.trim() || null,
    };

    const result = await createSource({ variables: { input } });
    const source = result.data?.sourceCreate;
    if (source?.id) {
      setSelectedSourceID(source.id);
      await sourcesQuery.refetch();

      if (form.syncAfterCreate && url) {
        await syncSourceByURL({ variables: { input: { url, source_id: source.id } } });
      }
    }

    setShowCreateDialog(false);
  }

  async function handleSyncSelected() {
    const url = selectedSource?.urls?.[0];
    if (!selectedSource || !url) {
      setError("Select a source with a URL before syncing.");
      return;
    }
    await syncSourceByURL({ variables: { input: { url, source_id: selectedSource.id } } });
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

  async function handleIgnoreSelected() {
    const selectedCandidates = candidates.filter((candidate) => selectedCandidateIDs.has(candidate.id));
    await Promise.all(selectedCandidates.map((candidate) => handleIgnore(candidate)));
    setSelectedCandidateIDs(new Set());
  }

  async function handleUnignore(item: IgnoredItem) {
    await unignoreSourceItem({
      variables: {
        input: {
          source_id: item.source_id,
          content_type: item.content_type,
          url: item.url,
        },
      },
    });
  }

  function handleCandidateSelected(
    candidate: CandidateScene,
    selected: boolean,
    _shiftKey: boolean
  ) {
    setSelectedCandidateIDs((current) => {
      const next = new Set(current);
      if (selected) {
        next.add(candidate.id);
      } else {
        next.delete(candidate.id);
      }
      return next;
    });
  }

  function handleSelectAllVisible() {
    const visibleCandidates = candidates.filter((candidate) => candidate.status !== "IGNORED");
    const allSelected = visibleCandidates.every((candidate) => selectedCandidateIDs.has(candidate.id));

    if (allSelected) {
      setSelectedCandidateIDs(new Set());
    } else {
      setSelectedCandidateIDs(new Set(visibleCandidates.map((candidate) => candidate.id)));
    }
  }

  const selectedCandidateCount = selectedCandidateIDs.size;
  const operations = (
    <ListOperations
      items={sources.length}
      hasSelection={false}
      operations={[
        {
          text: "New",
          onClick: () => setShowCreateDialog(true),
          isDisplayed: () => true,
          className: "create-new-item",
        },
      ]}
      operationsMenuClassName="source-list-operations-dropdown"
    />
  );

  return (
    <div className="sources-page">
      <Helmet title="Sources" />

      <div className="d-flex justify-content-between align-items-center mb-3 source-page-toolbar">
        <div>
          <h2>Sources</h2>
          <div className="text-muted">
            Review scraper-discovered media before promoting it into native Stash objects.
          </div>
        </div>
        {operations}
      </div>

      {error && <Alert variant="danger">{error}</Alert>}

      <Row>
        <Col lg={3} className="mb-3">
          <Card>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span>Sources</span>
              <Badge variant="secondary">{sources.length}</Badge>
            </Card.Header>
            <Card.Body className="source-list-panel">
              {sourcesQuery.loading && <div>Loading sources...</div>}
              {sources.map((source) => (
                <Card
                  key={source.id}
                  className={`source-summary-card mb-2 ${selectedSourceID === source.id ? "active" : ""}`}
                  onClick={() => setSelectedSourceID(source.id)}
                >
                  <Card.Body>
                    <div className="d-flex align-items-start">
                      {source.thumbnail_url && (
                        <img className="source-summary-thumb mr-2" src={source.thumbnail_url} alt="" />
                      )}
                      <div className="min-width-0 flex-grow-1">
                        <div className="d-flex justify-content-between align-items-start">
                          <strong className="source-summary-title text-truncate">{source.title}</strong>
                          <Badge variant="info" className="ml-2">{source.type}</Badge>
                        </div>
                        <div className="small text-muted text-truncate">{source.urls?.[0]}</div>
                        <div className="mt-2 small">
                          <Badge variant="warning" className="mr-1">{source.candidate_scene_count} videos</Badge>
                          <Badge variant="secondary">{source.ignored_count} ignored</Badge>
                        </div>
                      </div>
                    </div>
                  </Card.Body>
                </Card>
              ))}
            </Card.Body>
          </Card>
        </Col>

        <Col lg={9}>
          {selectedSource ? (
            <>
              <Card className="mb-3 source-detail-card">
                <Card.Body>
                  <div className="d-flex justify-content-between align-items-start flex-wrap">
                    <div className="source-detail-title-block">
                      <h3>{selectedSource.title}</h3>
                      <div className="text-muted small text-break">{selectedSource.urls?.[0]}</div>
                      {selectedSource.details && (
                        <div className="mt-2 source-detail-description">{selectedSource.details}</div>
                      )}
                    </div>
                    <div className="source-detail-actions mt-2 mt-md-0">
                      <Button
                        variant="outline-primary"
                        onClick={handleSyncSelected}
                        disabled={syncState.loading || !selectedSource.urls?.[0]}
                      >
                        {syncState.loading ? "Syncing..." : "Sync Source"}
                      </Button>
                    </div>
                  </div>
                  <div className="mt-3">
                    <Badge variant="info" className="mr-1">{selectedSource.type}</Badge>
                    <Badge variant="warning" className="mr-1">{selectedSource.candidate_scene_count} videos</Badge>
                    <Badge variant="secondary" className="mr-1">{selectedSource.ignored_count} ignored</Badge>
                    {selectedSource.last_synced_at && (
                      <span className="small text-muted">Last synced: {selectedSource.last_synced_at}</span>
                    )}
                  </div>
                </Card.Body>
              </Card>

              <Tabs defaultActiveKey="details" id="source-detail-tabs">
                <Tab eventKey="details" title="Details">
                  <Card className="mt-3">
                    <Card.Body>
                      <dl className="row mb-0">
                        <dt className="col-sm-3">Title</dt>
                        <dd className="col-sm-9">{selectedSource.title}</dd>
                        <dt className="col-sm-3">Type</dt>
                        <dd className="col-sm-9">{selectedSource.type}</dd>
                        <dt className="col-sm-3">URLs</dt>
                        <dd className="col-sm-9">
                          {selectedSource.urls.map((url) => (
                            <div key={url} className="text-break">{url}</div>
                          ))}
                        </dd>
                        <dt className="col-sm-3">Details</dt>
                        <dd className="col-sm-9">{selectedSource.details || ""}</dd>
                      </dl>
                    </Card.Body>
                  </Card>
                </Tab>

                <Tab eventKey="videos" title={`Videos (${candidates.length})`}>
                  <div className="pt-3">
                    <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap">
                      <div>
                        {candidateQuery.loading && <span className="text-muted">Loading candidates...</span>}
                        {!candidateQuery.loading && (
                          <span className="text-muted">{candidates.length} candidate videos</span>
                        )}
                      </div>
                      <ButtonGroup size="sm">
                        <Button variant="outline-secondary" onClick={handleSelectAllVisible}>
                          {selectedCandidateCount ? "Clear selection" : "Select all"}
                        </Button>
                        <Button
                          variant="outline-secondary"
                          onClick={handleIgnoreSelected}
                          disabled={selectedCandidateCount === 0}
                        >
                          Ignore selected
                        </Button>
                      </ButtonGroup>
                    </div>

                    <div className="source-candidate-grid">
                      {candidates.map((candidate) => (
                        <CandidateSceneCard
                          key={candidate.id}
                          candidate={candidate}
                          selected={selectedCandidateIDs.has(candidate.id)}
                          onSelectedChanged={handleCandidateSelected}
                          onIgnore={handleIgnore}
                        />
                      ))}
                    </div>
                  </div>
                </Tab>

                <Tab eventKey="images" title="Images">
                  <div className="pt-3 text-muted">Image candidate review will use the same native review pattern next.</div>
                </Tab>
                <Tab eventKey="galleries" title="Galleries">
                  <div className="pt-3 text-muted">Gallery candidate review will use gallery-native cards next.</div>
                </Tab>
                <Tab eventKey="groups" title="Groups">
                  <div className="pt-3 text-muted">Group candidate review is reserved for source-discovered group collections.</div>
                </Tab>
                <Tab eventKey="sources" title="Sources">
                  <div className="pt-3 text-muted">Child source candidates will appear here when source discovery is enabled.</div>
                </Tab>
                <Tab eventKey="ignored" title={`Ignored (${ignoredItems.length})`}>
                  <div className="pt-3">
                    {ignoredQuery.loading && <div>Loading ignored items...</div>}
                    {ignoredItems.length === 0 && !ignoredQuery.loading && (
                      <Alert variant="secondary">No ignored media for this source.</Alert>
                    )}
                    {ignoredItems.map((item) => (
                      <Card key={item.id} className="mb-2">
                        <Card.Body className="d-flex justify-content-between align-items-start">
                          <div className="min-width-0">
                            <strong>{item.title || item.url}</strong>
                            <div className="small text-muted text-break">{item.url}</div>
                            <Badge variant="secondary" className="mt-2">{item.content_type}</Badge>
                          </div>
                          <Button size="sm" variant="outline-primary" onClick={() => handleUnignore(item)}>
                            Unignore
                          </Button>
                        </Card.Body>
                      </Card>
                    ))}
                  </div>
                </Tab>
              </Tabs>
            </>
          ) : (
            <Alert variant="info">Create or select a source to review candidate media.</Alert>
          )}
        </Col>
      </Row>

      <SourceCreateDialog
        show={showCreateDialog}
        sources={sources}
        loading={createState.loading || syncState.loading}
        onHide={() => setShowCreateDialog(false)}
        onCreate={handleCreateSource}
      />
    </div>
  );
};

export default Sources;
