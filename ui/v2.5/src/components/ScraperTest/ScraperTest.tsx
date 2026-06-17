import React, { useEffect, useMemo, useState } from "react";
import { gql } from "@apollo/client";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Form,
  Row,
  Spinner,
} from "react-bootstrap";
import * as GQL from "src/core/generated-graphql";
import { SceneScrapeDialog } from "src/components/Scenes/SceneDetails/SceneScrapeDialog";
import { SceneCard } from "src/components/Scenes/SceneCard";
import { getClient } from "src/core/StashService";

const contentTypes = [{ label: "Scene", value: "SCENE" }];

type ScrapeType = "NAME" | "FRAGMENT" | "URL";

type ScraperSpec = {
  urls?: string[] | null;
  supported_scrapes: ScrapeType[];
};

type Scraper = {
  id: string;
  name: string;
  scene?: ScraperSpec | null;
};

type ScrapedSceneOnlineStream = {
  label?: string | null;
  kind: string;
  url: string;
  position: number;
  is_primary: boolean;
};

type ScrapedSceneOnlineMedia = {
  source_name: string;
  source_slug: string;
  external_id?: string | null;
  embed_url?: string | null;
  direct_video_url?: string | null;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  external_view_count?: number | null;
  raw_metadata_json?: string | null;
  streams: ScrapedSceneOnlineStream[];
};

type ScrapedSceneWithOnlineMedia = GQL.ScrapedScene & {
  online_media?: ScrapedSceneOnlineMedia | null;
};

type UIConfiguration = {
  kOptions?: {
    enableOnlineScenes?: boolean;
  };
};

type SceneCreateInput = {
  title?: string | null;
  code?: string | null;
  details?: string | null;
  director?: string | null;
  urls?: string[];
  date?: string | null;
  cover_image?: string | null;
  studio_id?: string | null;
  performer_ids?: string[];
  tag_ids?: string[];
};

type SceneOnlineMediaInput = {
  scene_id: string;
  source_name: string;
  source_slug: string;
  external_id?: string | null;
  embed_url?: string | null;
  direct_video_url?: string | null;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  external_view_count?: number | null;
  raw_metadata_json?: string | null;
  streams: Array<{
    label?: string | null;
    kind: string;
    url: string;
    position: number;
    is_primary: boolean;
  }>;
};

const LIST_SCRAPERS = gql`
  query ScraperTestListScrapers($types: [ScrapeContentType!]!) {
    listScrapers(types: $types) {
      id
      name
      scene {
        urls
        supported_scrapes
      }
    }
  }
`;

const GET_K_OPTIONS = gql`
  query ScraperTestKOptions {
    configuration {
      ui
    }
  }
`;

const SCRAPE_SCENE_URL = gql`
  query ScraperTestScrapeSceneURL($url: String!) {
    scrapeSceneURL(url: $url) {
      title
      code
      details
      director
      urls
      date
      image
      remote_site_id
      duration
      online_media {
        source_name
        source_slug
        external_id
        embed_url
        direct_video_url
        thumbnail_url
        duration_seconds
        external_view_count
        raw_metadata_json
        streams {
          label
          kind
          url
          position
          is_primary
        }
      }
      studio {
        stored_id
        name
        urls
        remote_site_id
      }
      performers {
        stored_id
        name
        remote_site_id
      }
      groups {
        stored_id
        name
      }
      tags {
        stored_id
        name
        remote_site_id
      }
    }
  }
`;

const CREATE_SCENE = gql`
  mutation ScraperTestCreateOnlineScene($input: SceneCreateInput!) {
    sceneCreate(input: $input) {
      id
      title
    }
  }
`;

const SAVE_ONLINE_MEDIA = gql`
  mutation ScraperTestSaveOnlineMedia($input: SceneOnlineMediaInput!) {
    sceneOnlineMediaSave(input: $input) {
      id
      scene_id
      embed_url
      direct_video_url
      external_view_count
    }
  }
`;

function formatJSON(value: unknown) {
  return value ? JSON.stringify(value, null, 2) : "";
}

function scraperSupportsURL(scraper: Scraper) {
  return scraper.scene?.supported_scrapes?.includes("URL") ?? false;
}

function scraperURLPatterns(scraper: Scraper) {
  return scraper.scene?.urls?.filter(Boolean) ?? [];
}

function urlLooksSupportedByScraper(scraper: Scraper, url: string) {
  const patterns = scraperURLPatterns(scraper);
  if (patterns.length === 0) return true;
  return patterns.some((pattern) => url.includes(pattern));
}

function getOnlineMedia(scene: ScrapedSceneWithOnlineMedia | null) {
  return scene?.online_media ?? null;
}

function storedIDs<T extends { stored_id?: string | null }>(items?: T[] | null) {
  return (items ?? [])
    .map((item) => item.stored_id)
    .filter((id): id is string => !!id);
}

function makeVirtualScene(scene: GQL.ScrapedScene): GQL.SlimSceneDataFragment {
  return {
    id: "scraper-test-virtual-scene",
    title: scene.title ?? "",
    code: scene.code ?? "",
    details: scene.details ?? "",
    director: scene.director ?? "",
    urls: scene.urls ?? [],
    date: scene.date ?? "",
    rating100: null,
    organized: false,
    o_counter: null,
    interactive_speed: null,
    resume_time: null,
    paths: {
      screenshot: scene.image ?? "",
      preview: "",
      stream: "",
      webp: "",
      vtt: "",
      sprite: "",
      funscript: "",
      interactive_heatmap: "",
    },
    files: [],
    studio: scene.studio
      ? ({
          id: scene.studio.stored_id ?? "scraper-test-virtual-studio",
          name: scene.studio.name,
          image_path: "",
        } as GQL.StudioDataFragment)
      : null,
    tags: (scene.tags ?? []).map((tag, index) =>
      ({
        id: tag.stored_id ?? `scraper-test-virtual-tag-${index}`,
        name: tag.name,
        aliases: [],
        image_path: null,
      } as GQL.TagDataFragment)
    ),
    performers: [],
    groups: [],
    galleries: [],
    scene_markers: [],
  } as unknown as GQL.SlimSceneDataFragment;
}

function buildSceneCreateInput(scene: ScrapedSceneWithOnlineMedia): SceneCreateInput {
  const urls = (scene.urls ?? []).filter(Boolean);
  const performerIDs = storedIDs(scene.performers);
  const tagIDs = storedIDs(scene.tags);

  return {
    title: scene.title || undefined,
    code: scene.code || undefined,
    details: scene.details || undefined,
    director: scene.director || undefined,
    urls: urls.length ? urls : undefined,
    date: scene.date || undefined,
    cover_image: scene.image || getOnlineMedia(scene)?.thumbnail_url || undefined,
    studio_id: scene.studio?.stored_id || undefined,
    performer_ids: performerIDs.length ? performerIDs : undefined,
    tag_ids: tagIDs.length ? tagIDs : undefined,
  };
}

function buildOnlineMediaInput(
  sceneID: string,
  scene: ScrapedSceneWithOnlineMedia,
  media: ScrapedSceneOnlineMedia
): SceneOnlineMediaInput {
  const streams = (media.streams ?? [])
    .filter((stream) => !!stream.url)
    .map((stream, index) => ({
      label: stream.label || undefined,
      kind: stream.kind || "embed",
      url: stream.url,
      position: stream.position ?? index,
      is_primary: stream.is_primary ?? index === 0,
    }));

  if (streams.length === 0 && media.embed_url) {
    streams.push({
      label: "Primary embed",
      kind: "embed",
      url: media.embed_url,
      position: 0,
      is_primary: true,
    });
  }

  if (streams.length === 0 && media.direct_video_url) {
    streams.push({
      label: "Direct video",
      kind: "direct",
      url: media.direct_video_url,
      position: 0,
      is_primary: true,
    });
  }

  return {
    scene_id: sceneID,
    source_name: media.source_name || "Unknown",
    source_slug: media.source_slug || "unknown",
    external_id: media.external_id || scene.remote_site_id || undefined,
    embed_url: media.embed_url || undefined,
    direct_video_url: media.direct_video_url || undefined,
    thumbnail_url: media.thumbnail_url || scene.image || undefined,
    duration_seconds: media.duration_seconds ?? scene.duration ?? undefined,
    external_view_count: media.external_view_count ?? undefined,
    raw_metadata_json: media.raw_metadata_json || undefined,
    streams,
  };
}

export const ScraperTest: React.FC = () => {
  const [url, setURL] = useState("");
  const [contentType, setContentType] = useState(contentTypes[0].value);
  const [scrapers, setScrapers] = useState<Scraper[]>([]);
  const [selectedScraperID, setSelectedScraperID] = useState("");
  const [loadingScrapers, setLoadingScrapers] = useState(false);
  const [testing, setTesting] = useState(false);
  const [creatingOnlineScene, setCreatingOnlineScene] = useState(false);
  const [onlineScenesEnabled, setOnlineScenesEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createdSceneID, setCreatedSceneID] = useState<string | null>(null);
  const [result, setResult] = useState<ScrapedSceneWithOnlineMedia | null>(null);
  const [rawResult, setRawResult] = useState<unknown>(null);
  const [showScrapeDialog, setShowScrapeDialog] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadKOptions() {
      try {
        const response = await getClient().query<{
          configuration: { ui?: UIConfiguration | null };
        }>({
          query: GET_K_OPTIONS,
          fetchPolicy: "network-only",
        });

        if (!cancelled) {
          setOnlineScenesEnabled(
            response.data.configuration.ui?.kOptions?.enableOnlineScenes !== false
          );
        }
      } catch {
        if (!cancelled) setOnlineScenesEnabled(true);
      }
    }

    loadKOptions();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadScrapers() {
      setLoadingScrapers(true);
      setError(null);

      try {
        const response = await getClient().query<{
          listScrapers: Scraper[];
        }>({
          query: LIST_SCRAPERS,
          variables: { types: [contentType] },
          fetchPolicy: "network-only",
        });

        if (cancelled) return;

        const nextScrapers = response.data.listScrapers ?? [];
        setScrapers(nextScrapers);
        setSelectedScraperID((currentID) => {
          if (nextScrapers.some((scraper) => scraper.id === currentID)) return currentID;
          const urlScraper = nextScrapers.find(scraperSupportsURL);
          return urlScraper?.id ?? nextScrapers[0]?.id ?? "";
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : `${err}`);
          setScrapers([]);
          setSelectedScraperID("");
        }
      } finally {
        if (!cancelled) setLoadingScrapers(false);
      }
    }

    loadScrapers();
    return () => {
      cancelled = true;
    };
  }, [contentType]);

  const selectedScraper = useMemo(
    () => scrapers.find((scraper) => scraper.id === selectedScraperID),
    [scrapers, selectedScraperID]
  );

  const virtualScene = useMemo(
    () => (result ? makeVirtualScene(result) : undefined),
    [result]
  );

  const onlineMedia = useMemo(() => getOnlineMedia(result), [result]);

  const urlSupportedBySelectedScraper = selectedScraper
    ? urlLooksSupportedByScraper(selectedScraper, url.trim())
    : false;

  const canTest =
    contentType === "SCENE" &&
    !!url.trim() &&
    !!selectedScraper &&
    scraperSupportsURL(selectedScraper) &&
    urlSupportedBySelectedScraper &&
    !testing;

  const canCreateOnlineScene =
    onlineScenesEnabled && !!result && !!onlineMedia && !creatingOnlineScene;

  async function testScraper() {
    if (!canTest || !selectedScraper) return;

    setTesting(true);
    setError(null);
    setCreatedSceneID(null);
    setResult(null);
    setRawResult(null);
    setShowScrapeDialog(false);

    try {
      const response = await getClient().query<{
        scrapeSceneURL: ScrapedSceneWithOnlineMedia | null;
      }>({
        query: SCRAPE_SCENE_URL,
        variables: { url: url.trim() },
        fetchPolicy: "network-only",
      });

      const scene = response.data.scrapeSceneURL ?? null;
      setResult(scene);
      setRawResult(response.data);
      setShowScrapeDialog(!!scene);

      if (!scene) setError("No scene result was returned for this URL.");
    } catch (err) {
      setError(err instanceof Error ? err.message : `${err}`);
    } finally {
      setTesting(false);
    }
  }

  async function createOnlineScene() {
    if (!result || !onlineMedia || !canCreateOnlineScene) return;

    setCreatingOnlineScene(true);
    setError(null);
    setCreatedSceneID(null);

    try {
      const sceneResponse = await getClient().mutate<{
        sceneCreate: { id: string } | null;
      }>({
        mutation: CREATE_SCENE,
        variables: { input: buildSceneCreateInput(result) },
      });

      const sceneID = sceneResponse.data?.sceneCreate?.id;
      if (!sceneID) throw new Error("Scene creation did not return a scene id.");

      await getClient().mutate({
        mutation: SAVE_ONLINE_MEDIA,
        variables: { input: buildOnlineMediaInput(sceneID, result, onlineMedia) },
      });

      setCreatedSceneID(sceneID);
    } catch (err) {
      setError(err instanceof Error ? err.message : `${err}`);
    } finally {
      setCreatingOnlineScene(false);
    }
  }

  function handleScrapeDialogClose(appliedScene?: GQL.ScrapedScene) {
    if (appliedScene && result) {
      setResult({ ...result, ...appliedScene });
    }
    setShowScrapeDialog(false);
  }

  return (
    <div className="mt-4">
      {showScrapeDialog && result && (
        <SceneScrapeDialog
          scene={{ title: "", urls: [], performer_ids: [], tag_ids: [], groups: [] }}
          sceneStudio={null}
          scenePerformers={[]}
          sceneTags={[]}
          sceneGroups={[]}
          scraped={result}
          endpoint={selectedScraper?.name}
          onClose={handleScrapeDialogClose}
        />
      )}

      <Row>
        <Col lg={5} xl={4}>
          <Card>
            <Card.Header>
              <h4 className="mb-0">Scraper Test</h4>
            </Card.Header>
            <Card.Body>
              <p className="text-muted">
                Test a native scene URL scraper against a URL without saving a scene.
              </p>

              {error && <Alert variant="danger">{error}</Alert>}
              {createdSceneID && (
                <Alert variant="success">
                  Online scene created. <a href={`/scenes/${createdSceneID}`}>Open scene</a>
                </Alert>
              )}
              {!onlineScenesEnabled && (
                <Alert variant="warning">
                  Online scenes are disabled in K-Options. You can still test scrapers,
                  but imports are disabled.
                </Alert>
              )}

              <Form>
                <Form.Group controlId="scraper-test-content-type">
                  <Form.Label>Content type</Form.Label>
                  <Form.Control
                    as="select"
                    value={contentType}
                    onChange={(event) => {
                      setContentType(event.currentTarget.value);
                      setResult(null);
                      setRawResult(null);
                      setCreatedSceneID(null);
                      setShowScrapeDialog(false);
                    }}
                  >
                    {contentTypes.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </Form.Control>
                </Form.Group>

                <Form.Group controlId="scraper-test-scraper">
                  <Form.Label>Scraper</Form.Label>
                  <Form.Control
                    as="select"
                    value={selectedScraperID}
                    disabled={loadingScrapers || scrapers.length === 0}
                    onChange={(event) => {
                      setSelectedScraperID(event.currentTarget.value);
                      setResult(null);
                      setRawResult(null);
                      setCreatedSceneID(null);
                      setShowScrapeDialog(false);
                    }}
                  >
                    {scrapers.length === 0 && <option>No scrapers loaded</option>}
                    {scrapers.map((scraper) => (
                      <option key={scraper.id} value={scraper.id}>
                        {scraper.name}
                      </option>
                    ))}
                  </Form.Control>
                  {selectedScraper && (
                    <Form.Text muted className="d-block">
                      Supports: {selectedScraper.scene?.supported_scrapes.join(", ")}
                    </Form.Text>
                  )}
                </Form.Group>

                <Form.Group controlId="scraper-test-url">
                  <Form.Label>URL</Form.Label>
                  <Form.Control
                    type="text"
                    value={url}
                    onChange={(event) => {
                      setURL(event.currentTarget.value);
                      setResult(null);
                      setRawResult(null);
                      setCreatedSceneID(null);
                      setShowScrapeDialog(false);
                    }}
                    placeholder="Paste a scene URL to test"
                  />
                </Form.Group>

                <Button type="button" variant="primary" disabled={!canTest} onClick={testScraper}>
                  {testing ? (
                    <>
                      <Spinner animation="border" size="sm" className="mr-2" />
                      Testing
                    </>
                  ) : (
                    "Test URL scrape"
                  )}
                </Button>

                {result && (
                  <Button
                    type="button"
                    variant="secondary"
                    className="ml-2"
                    onClick={() => setShowScrapeDialog(true)}
                  >
                    Review native scrape result
                  </Button>
                )}

                {result && onlineMedia && (
                  <Button
                    type="button"
                    variant="success"
                    className="ml-2"
                    disabled={!canCreateOnlineScene}
                    onClick={createOnlineScene}
                  >
                    {creatingOnlineScene ? (
                      <>
                        <Spinner animation="border" size="sm" className="mr-2" />
                        Creating
                      </>
                    ) : (
                      "Create Online Scene"
                    )}
                  </Button>
                )}

                {result && !onlineMedia && (
                  <Form.Text muted className="d-block mt-2">
                    This scrape result does not include online media metadata yet.
                  </Form.Text>
                )}

                {selectedScraper && !scraperSupportsURL(selectedScraper) && (
                  <Form.Text muted className="d-block mt-2">
                    Selected scraper does not support scene URL scraping.
                  </Form.Text>
                )}

                {selectedScraper &&
                  scraperSupportsURL(selectedScraper) &&
                  !urlSupportedBySelectedScraper &&
                  !!url.trim() && (
                    <Form.Text muted className="d-block mt-2">
                      URL does not match this scraper's URL patterns: {" "}
                      {scraperURLPatterns(selectedScraper).join(", ")}
                    </Form.Text>
                  )}
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={7} xl={8}>
          <Card className="mb-3">
            <Card.Header className="d-flex align-items-center justify-content-between">
              <h5 className="mb-0">Virtual Scene</h5>
              {result && <Badge variant="secondary">Not saved</Badge>}
            </Card.Header>
            <Card.Body>
              {!result && (
                <p className="text-muted mb-0">
                  Run a scraper to preview the scraped scene as a temporary Stash
                  scene entity here.
                </p>
              )}

              {result && virtualScene && (
                <>
                  <Alert variant="info">
                    This is a virtual scene assembled from the scraper result. It is
                    not saved to the database.
                  </Alert>

                  <Row>
                    <Col md={5} xl={4}>
                      <SceneCard scene={virtualScene} width={320} />
                    </Col>
                    <Col md={7} xl={8}>
                      <dl className="row mb-0">
                        <dt className="col-sm-3">Title</dt>
                        <dd className="col-sm-9">{result.title || "—"}</dd>

                        <dt className="col-sm-3">Date</dt>
                        <dd className="col-sm-9">{result.date || "—"}</dd>

                        <dt className="col-sm-3">Studio</dt>
                        <dd className="col-sm-9">{result.studio?.name || "—"}</dd>

                        <dt className="col-sm-3">Duration</dt>
                        <dd className="col-sm-9">
                          {result.duration ? `${result.duration}s` : "—"}
                        </dd>

                        <dt className="col-sm-3">Remote ID</dt>
                        <dd className="col-sm-9">{result.remote_site_id || "—"}</dd>

                        <dt className="col-sm-3">URLs</dt>
                        <dd className="col-sm-9">
                          {result.urls?.length ? result.urls.join(", ") : "—"}
                        </dd>

                        <dt className="col-sm-3">Tags</dt>
                        <dd className="col-sm-9">
                          {result.tags?.length
                            ? result.tags.map((tag) => tag.name).join(", ")
                            : "—"}
                        </dd>

                        <dt className="col-sm-3">Details</dt>
                        <dd className="col-sm-9">{result.details || "—"}</dd>
                      </dl>
                    </Col>
                  </Row>
                </>
              )}
            </Card.Body>
          </Card>

          <Card className="mb-3">
            <Card.Header>
              <h5 className="mb-0">Online Media</h5>
            </Card.Header>
            <Card.Body>
              {!onlineMedia && (
                <p className="text-muted mb-0">
                  Online media fields will appear here when the scraper returns them.
                </p>
              )}

              {onlineMedia && (
                <>
                  <dl className="row">
                    <dt className="col-sm-3">Source</dt>
                    <dd className="col-sm-9">{onlineMedia.source_name}</dd>

                    <dt className="col-sm-3">External ID</dt>
                    <dd className="col-sm-9">{onlineMedia.external_id || "—"}</dd>

                    <dt className="col-sm-3">Embed URL</dt>
                    <dd className="col-sm-9">{onlineMedia.embed_url || "—"}</dd>

                    <dt className="col-sm-3">Direct video URL</dt>
                    <dd className="col-sm-9">{onlineMedia.direct_video_url || "—"}</dd>

                    <dt className="col-sm-3">External views</dt>
                    <dd className="col-sm-9">
                      {onlineMedia.external_view_count ?? "—"}
                    </dd>
                  </dl>

                  <h6>Streams</h6>
                  {onlineMedia.streams.length === 0 ? (
                    <p className="text-muted mb-0">No streams returned.</p>
                  ) : (
                    <ul className="mb-0">
                      {onlineMedia.streams.map((stream, index) => (
                        <li key={`${stream.url}-${index}`}>
                          {stream.label || `Stream ${index + 1}`} · {stream.kind} ·{" "}
                          {stream.is_primary ? "primary" : "backup"} · {stream.url}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </Card.Body>
          </Card>

          <Card>
            <Card.Header>
              <h5 className="mb-0">Raw GraphQL Output</h5>
            </Card.Header>
            <Card.Body>
              <Form.Control
                as="textarea"
                rows={16}
                readOnly
                value={formatJSON(rawResult)}
                placeholder="Scraper output will appear here."
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ScraperTest;
