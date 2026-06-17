import React, { useEffect, useMemo, useState } from "react";
import { gql } from "@apollo/client";
import { FormattedMessage, useIntl } from "react-intl";
import { useHistory, useLocation } from "react-router-dom";
import { SceneEditPanel } from "./SceneEditPanel";
import * as GQL from "src/core/generated-graphql";
import { getClient, mutateCreateScene, useFindScene } from "src/core/StashService";
import ImageUtils from "src/utils/image";
import { LoadingIndicator } from "src/components/Shared/LoadingIndicator";
import { useToast } from "src/hooks/Toast";

type ScrapedOnlineStream = {
  label?: string | null;
  kind: string;
  url: string;
  position: number;
  is_primary: boolean;
};

type ScrapedOnlineMedia = {
  source_name: string;
  source_slug: string;
  external_id?: string | null;
  embed_url?: string | null;
  direct_video_url?: string | null;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  external_view_count?: number | null;
  raw_metadata_json?: string | null;
  streams: ScrapedOnlineStream[];
};

type ScrapedStoredEntity = {
  stored_id?: string | null;
  name?: string | null;
  remote_site_id?: string | null;
};

type ScrapedSceneWithOnlineMedia = {
  title?: string | null;
  code?: string | null;
  details?: string | null;
  director?: string | null;
  urls?: string[] | null;
  date?: string | null;
  image?: string | null;
  remote_site_id?: string | null;
  duration?: number | null;
  studio?: (ScrapedStoredEntity & { urls?: string[] | null }) | null;
  performers?: ScrapedStoredEntity[] | null;
  groups?: ScrapedStoredEntity[] | null;
  tags?: ScrapedStoredEntity[] | null;
  online_media?: ScrapedOnlineMedia | null;
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

type ExistingScene = {
  id: string;
  title?: string | null;
  urls: string[];
};

const SCRAPE_ONLINE_SCENE_URL = gql`
  query SceneCreateScrapeOnlineSceneURL($url: String!) {
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

const FIND_DUPLICATE_SCENE_BY_URL = gql`
  query SceneCreateFindDuplicateSceneByURL($url: String!) {
    findScenes(
      filter: { per_page: 1 }
      scene_filter: { url: { value: $url, modifier: EQUALS } }
    ) {
      count
      scenes {
        id
        title
        urls
      }
    }
  }
`;

const SAVE_ONLINE_MEDIA = gql`
  mutation SceneCreateSaveOnlineMedia($input: SceneOnlineMediaInput!) {
    sceneOnlineMediaSave(input: $input) {
      id
      scene_id
    }
  }
`;

function storedIDs(items?: ScrapedStoredEntity[] | null) {
  return (items ?? [])
    .map((item) => item.stored_id)
    .filter((id): id is string => !!id);
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function normalizeURLForDuplicateCheck(value?: string | null) {
  return value?.trim() ?? "";
}

function duplicateCandidateURLs(
  scene: ScrapedSceneWithOnlineMedia,
  sourceURL: string
) {
  return uniqueStrings(
    [sourceURL, ...(scene.urls ?? [])].map(normalizeURLForDuplicateCheck)
  );
}

async function findExistingSceneByURL(url: string): Promise<ExistingScene | null> {
  const response = await getClient().query<{
    findScenes: { count: number; scenes: ExistingScene[] };
  }>({
    query: FIND_DUPLICATE_SCENE_BY_URL,
    variables: { url },
    fetchPolicy: "network-only",
  });

  return response.data.findScenes.scenes[0] ?? null;
}

async function findExistingSceneForURLs(urls: string[]) {
  for (const candidateURL of urls) {
    const scene = await findExistingSceneByURL(candidateURL);
    if (scene) return scene;
  }

  return null;
}

function buildScrapedSceneInput(
  scene: ScrapedSceneWithOnlineMedia,
  sourceURL: string
): GQL.SceneCreateInput {
  const urls = uniqueStrings([...(scene.urls ?? []), sourceURL]);
  const performerIDs = storedIDs(scene.performers);
  const tagIDs = storedIDs(scene.tags);

  return {
    title: scene.title || undefined,
    code: scene.code || undefined,
    details: scene.details || undefined,
    director: scene.director || undefined,
    urls: urls.length ? urls : undefined,
    date: scene.date || undefined,
    cover_image: scene.image || scene.online_media?.thumbnail_url || undefined,
    studio_id: scene.studio?.stored_id || undefined,
    performer_ids: performerIDs.length ? performerIDs : undefined,
    tag_ids: tagIDs.length ? tagIDs : undefined,
  };
}

function hasValues<T>(items?: T[] | null): items is T[] {
  return Array.isArray(items) && items.length > 0;
}

function mergeSceneCreateInput(
  scraped: GQL.SceneCreateInput,
  manual: GQL.SceneCreateInput
): GQL.SceneCreateInput {
  return {
    ...manual,
    title: manual.title || scraped.title,
    code: manual.code || scraped.code,
    details: manual.details || scraped.details,
    director: manual.director || scraped.director,
    urls: hasValues(manual.urls) ? manual.urls : scraped.urls,
    date: manual.date || scraped.date,
    cover_image:
      manual.cover_image !== undefined && manual.cover_image !== null
        ? manual.cover_image
        : scraped.cover_image,
    studio_id: manual.studio_id || scraped.studio_id,
    performer_ids: hasValues(manual.performer_ids)
      ? manual.performer_ids
      : scraped.performer_ids,
    tag_ids: hasValues(manual.tag_ids) ? manual.tag_ids : scraped.tag_ids,
  };
}

function buildOnlineMediaInput(
  sceneID: string,
  scene: ScrapedSceneWithOnlineMedia,
  media: ScrapedOnlineMedia
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

const SceneCreate: React.FC = () => {
  const history = useHistory();
  const intl = useIntl();
  const Toast = useToast();

  const location = useLocation();
  const query = useMemo(() => new URLSearchParams(location.search), [location]);

  // create scene from provided scene id if applicable
  const { data, loading } = useFindScene(query.get("from_scene_id") ?? "new");
  const [loadingCoverImage, setLoadingCoverImage] = useState(false);
  const [coverImage, setCoverImage] = useState<string>();

  const scene = useMemo(() => {
    if (data?.findScene) {
      return {
        ...data.findScene,
        paths: undefined,
        id: undefined,
      };
    }

    return {
      title: query.get("q") ?? undefined,
    };
  }, [data?.findScene, query]);

  useEffect(() => {
    async function fetchCoverImage() {
      const srcScene = data?.findScene;
      if (srcScene?.paths.screenshot) {
        setLoadingCoverImage(true);
        const imageData = await ImageUtils.imageToDataURL(
          srcScene.paths.screenshot
        );
        setCoverImage(imageData);
        setLoadingCoverImage(false);
      } else {
        setCoverImage(undefined);
      }
    }

    fetchCoverImage();
  }, [data?.findScene]);

  if (loading || loadingCoverImage) {
    return <LoadingIndicator />;
  }

  async function scrapeOnlineScene(sourceURL: string) {
    const response = await getClient().query<{
      scrapeSceneURL: ScrapedSceneWithOnlineMedia | null;
    }>({
      query: SCRAPE_ONLINE_SCENE_URL,
      variables: { url: sourceURL },
      fetchPolicy: "network-only",
    });

    const scrapedScene = response.data.scrapeSceneURL;
    if (!scrapedScene) {
      throw new Error("No scene scraper result was returned for this URL.");
    }

    if (!scrapedScene.online_media) {
      throw new Error("This URL was scraped, but it did not return online media.");
    }

    return scrapedScene;
  }

  async function createScene(input: GQL.SceneCreateInput) {
    const fileID = query.get("file_id") ?? undefined;
    const result = await mutateCreateScene({
      ...input,
      file_ids: fileID ? [fileID] : undefined,
    });

    const sceneID = result.data?.sceneCreate?.id;
    if (!sceneID) {
      throw new Error("Scene creation did not return a scene id.");
    }

    return sceneID;
  }

  function onCreateSuccess(sceneID: string, andNew?: boolean) {
    if (!andNew) {
      history.push(`/scenes/${sceneID}`);
    }

    Toast.success(
      intl.formatMessage(
        { id: "toast.created_entity" },
        { entity: intl.formatMessage({ id: "scene" }).toLocaleLowerCase() }
      )
    );
  }

  function onDuplicateFound(scene: ExistingScene) {
    history.push(`/scenes/${scene.id}`);
    Toast.success("Scene already exists for this source URL. Opened existing scene.");
  }

  async function onSave(
    input: GQL.SceneCreateInput,
    andNew?: boolean,
    onlineSourceURL?: string
  ) {
    if (!onlineSourceURL) {
      const sceneID = await createScene(input);
      onCreateSuccess(sceneID, andNew);
      return;
    }

    const scrapedScene = await scrapeOnlineScene(onlineSourceURL);
    const existingScene = await findExistingSceneForURLs(
      duplicateCandidateURLs(scrapedScene, onlineSourceURL)
    );
    if (existingScene) {
      onDuplicateFound(existingScene);
      return;
    }

    const mergedInput = mergeSceneCreateInput(
      buildScrapedSceneInput(scrapedScene, onlineSourceURL),
      input
    );
    const sceneID = await createScene(mergedInput);

    await getClient().mutate({
      mutation: SAVE_ONLINE_MEDIA,
      variables: {
        input: buildOnlineMediaInput(
          sceneID,
          scrapedScene,
          scrapedScene.online_media!
        ),
      },
    });

    onCreateSuccess(sceneID, andNew);
  }

  return (
    <div className="row new-view justify-content-center" id="create-scene-page">
      <div className="col-md-8">
        <h2>
          <FormattedMessage
            id="actions.create_entity"
            values={{ entityType: intl.formatMessage({ id: "scene" }) }}
          />
        </h2>
        <SceneEditPanel
          scene={scene}
          initialCoverImage={coverImage}
          isVisible
          isNew
          onSubmit={onSave}
        />
      </div>
    </div>
  );
};

export default SceneCreate;
