import React, { useEffect, useMemo, useState } from "react";
import { gql } from "@apollo/client";
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner } from "react-bootstrap";
import * as GQL from "src/core/generated-graphql";
import { SceneScrapeDialog } from "src/components/Scenes/SceneDetails/SceneScrapeDialog";
import { SceneCard } from "src/components/Scenes/SceneCard";
import { getClient } from "../../core/StashService";

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

const SCRAPE_SCENE_WITH_SELECTED_SCRAPER = gql`
  query ScraperTestScrapeScene($scraperID: ID!, $url: String!) {
    scrapeSingleScene(
      source: { scraper_id: $scraperID }
      input: { scene_input: { urls: [$url] } }
    ) {
      title
      code
      details
      director
      urls
      date
      image
      remote_site_id
      duration
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
        remote_site_id
      }
      tags {
        stored_id
        name
        remote_site_id
      }
    }
  }
`;

function formatJSON(value: unknown) {
  if (!value) {
    return "";
  }

  return JSON.stringify(value, null, 2);
}

function scraperSupportsFragment(scraper: Scraper) {
  return scraper.scene?.supported_scrapes?.includes("FRAGMENT") ?? false;
}

function scraperSupportsURL(scraper: Scraper) {
  return scraper.scene?.supported_scrapes?.includes("URL") ?? false;
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

export const ScraperTest: React.FC = () => {
  const [url, setURL] = useState("");
  const [contentType, setContentType] = useState(contentTypes[0].value);
  const [scrapers, setScrapers] = useState<Scraper[]>([]);
  const [selectedScraperID, setSelectedScraperID] = useState("");
  const [loadingScrapers, setLoadingScrapers] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GQL.ScrapedScene | null>(null);
  const [rawResult, setRawResult] = useState<unknown>(null);
  const [showScrapeDialog, setShowScrapeDialog] = useState(false);

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

        if (cancelled) {
          return;
        }

        const nextScrapers = response.data.listScrapers ?? [];
        setScrapers(nextScrapers);

        setSelectedScraperID((currentID) => {
          if (nextScrapers.some((scraper) => scraper.id === currentID)) {
            return currentID;
          }

          const fragmentScraper = nextScrapers.find(scraperSupportsFragment);
          return fragmentScraper?.id ?? nextScrapers[0]?.id ?? "";
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : `${err}`);
          setScrapers([]);
          setSelectedScraperID("");
        }
      } finally {
        if (!cancelled) {
          setLoadingScrapers(false);
        }
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

  const canTest =
    contentType === "SCENE" &&
    !!url.trim() &&
    !!selectedScraper &&
    scraperSupportsFragment(selectedScraper) &&
    !testing;

  async function testScraper() {
    if (!canTest || !selectedScraper) {
      return;
    }

    setTesting(true);
    setError(null);
    setResult(null);
    setRawResult(null);
    setShowScrapeDialog(false);

    try {
      const response = await getClient().query<{
        scrapeSingleScene: GQL.ScrapedScene[];
      }>({
        query: SCRAPE_SCENE_WITH_SELECTED_SCRAPER,
        variables: {
          scraperID: selectedScraper.id,
          url: url.trim(),
        },
        fetchPolicy: "network-only",
      });

      const scene = response.data.scrapeSingleScene?.[0] ?? null;
      setResult(scene);
      setRawResult(response.data);
      setShowScrapeDialog(!!scene);

      if (!scene) {
        setError("Selected scraper returned no scene result.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `${err}`);
    } finally {
      setTesting(false);
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
          scene={{
            title: "",
            urls: [],
            performer_ids: [],
            tag_ids: [],
            groups: [],
          }}
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
                Test a selected native scene scraper against a URL without saving a
                scene.
              </p>

              {error && <Alert variant="danger">{error}</Alert>}

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
                    onChange={(event) => setURL(event.currentTarget.value)}
                    placeholder="Paste a scene URL to test"
                  />
                </Form.Group>

                <Button
                  type="button"
                  variant="primary"
                  disabled={!canTest}
                  onClick={testScraper}
                >
                  {testing ? (
                    <>
                      <Spinner animation="border" size="sm" className="mr-2" />
                      Testing
                    </>
                  ) : (
                    "Test selected scraper"
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

                {selectedScraper && !scraperSupportsFragment(selectedScraper) && (
                  <Form.Text muted className="d-block mt-2">
                    Selected scraper does not support scene fragment scraping. URL
                    preview uses the selected scraper through Stash's native fragment
                    scrape path.
                  </Form.Text>
                )}

                {selectedScraper && scraperSupportsURL(selectedScraper) && (
                  <Form.Text muted className="d-block mt-2">
                    This scraper also supports native URL scraping.
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
