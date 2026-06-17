import React, { useEffect, useMemo, useRef, useState } from "react";
import { gql, useQuery } from "@apollo/client";
import { Alert, Button, Form } from "react-bootstrap";
import videojs from "video.js";
import { ErrorMessage } from "src/components/Shared/ErrorMessage";
import { LoadingIndicator } from "src/components/Shared/LoadingIndicator";
import { after, instead } from "src/patch";
import TextUtils from "src/utils/text";

interface IScenePlayerPatchProps {
  scene: {
    id: string;
    files: unknown[];
  };
}

interface ISceneCardImagePatchProps {
  scene: {
    id: string;
    files: unknown[];
  };
  selecting?: boolean;
}

interface ISceneCardSceneSpecsPatchProps {
  scene: {
    id: string;
    files: unknown[];
  };
}

interface IOnlineStream {
  id?: string;
  label?: string | null;
  kind: string;
  url: string;
  position: number;
  is_primary: boolean;
}

interface IOnlineMedia {
  source_name: string;
  source_slug: string;
  external_id?: string | null;
  page_url: string;
  canonical_url?: string | null;
  embed_url?: string | null;
  direct_video_url?: string | null;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  external_view_count?: number | null;
  streams: IOnlineStream[];
}

interface IOnlineMediaData {
  findScene?: {
    id: string;
    online_media?: IOnlineMedia | null;
  } | null;
}

interface IOnlineDurationData {
  findScene?: {
    id: string;
    online_media?: {
      duration_seconds?: number | null;
    } | null;
  } | null;
}

interface IOnlinePreviewData {
  findScene?: {
    id: string;
    online_media?: {
      direct_video_url?: string | null;
      thumbnail_url?: string | null;
    } | null;
  } | null;
}

interface IOnlineMediaVariables {
  id: string;
}

const FIND_SCENE_ONLINE_MEDIA = gql`
  query FindSceneOnlineMedia($id: ID!) {
    findScene(id: $id) {
      id
      online_media {
        source_name
        source_slug
        external_id
        page_url
        canonical_url
        embed_url
        direct_video_url
        thumbnail_url
        duration_seconds
        external_view_count
        streams {
          id
          label
          kind
          url
          position
          is_primary
        }
      }
    }
  }
`;

const FIND_SCENE_ONLINE_DURATION = gql`
  query FindSceneOnlineDuration($id: ID!) {
    findScene(id: $id) {
      id
      online_media {
        duration_seconds
      }
    }
  }
`;

const FIND_SCENE_ONLINE_PREVIEW = gql`
  query FindSceneOnlinePreview($id: ID!) {
    findScene(id: $id) {
      id
      online_media {
        direct_video_url
        thumbnail_url
      }
    }
  }
`;

function isDirectStream(stream: IOnlineStream) {
  return (
    stream.kind === "direct" || /\.(?:mp4|m3u8)(?:$|[?#])/i.test(stream.url)
  );
}

function isHLSURL(url: string) {
  return /\.m3u8(?:$|[?#])/i.test(url);
}

function streamQualityRank(stream: IOnlineStream) {
  const labelHeight = /(?:^|\D)(\d{3,4})p(?:\D|$)/i.exec(stream.label ?? "");
  if (labelHeight) {
    return Number.parseInt(labelHeight[1], 10);
  }

  return isDirectStream(stream) ? 1 : 0;
}

function dedupeStreams(streams: IOnlineStream[]) {
  const seen = new Set<string>();
  const ret: IOnlineStream[] = [];

  for (const stream of streams) {
    if (!stream.url || seen.has(stream.url)) {
      continue;
    }

    seen.add(stream.url);
    ret.push(stream);
  }

  return ret;
}

function buildPlaybackStreams(media: IOnlineMedia): IOnlineStream[] {
  const streams = [...(media.streams ?? [])].sort((a, b) => a.position - b.position);

  if (media.direct_video_url && !streams.some((stream) => stream.url === media.direct_video_url)) {
    streams.push({
      label: "Direct video",
      kind: "direct",
      url: media.direct_video_url,
      position: streams.length,
      is_primary: streams.length === 0,
    });
  }

  if (media.embed_url && !streams.some((stream) => stream.url === media.embed_url)) {
    streams.push({
      label: "Primary embed",
      kind: "embed",
      url: media.embed_url,
      position: streams.length,
      is_primary: streams.length === 0,
    });
  }

  const directStreams = dedupeStreams(streams.filter(isDirectStream));
  const playbackStreams = directStreams.length > 0 ? directStreams : dedupeStreams(streams);

  return playbackStreams.sort(
    (a, b) =>
      streamQualityRank(b) - streamQualityRank(a) ||
      a.position - b.position
  );
}

const onlinePlayerStyle = `
  .online-scene-player {
    min-height: 0;
    overflow: visible;
    position: relative;
  }

  .online-scene-player__frame {
    min-height: 0;
    overflow: visible;
    position: relative;
  }

  .online-scene-player__frame iframe,
  .online-scene-player__frame video {
    display: block;
    object-fit: contain;
  }

  .online-scene-player__controls {
    align-items: center;
    bottom: -2rem;
    display: flex;
    gap: 0.35rem;
    justify-content: flex-end;
    opacity: 0.3;
    position: absolute;
    right: 0.25rem;
    transition: opacity 120ms ease-in-out;
    z-index: 4;
  }

  .online-scene-player__controls:hover,
  .online-scene-player__controls:focus-within {
    opacity: 1;
  }

  .online-scene-player__server {
    background-color: rgba(10, 18, 24, 0.72);
    border-color: rgba(255, 255, 255, 0.2);
    color: #fff;
    height: calc(1.5em + 0.35rem + 2px);
    max-width: 10rem;
    min-width: 8rem;
    order: 2;
    padding-bottom: 0.1rem;
    padding-top: 0.1rem;
  }

  .online-scene-player__source-button.btn {
    background-color: rgba(10, 18, 24, 0.65);
    border-color: rgba(255, 255, 255, 0.18);
    color: #fff;
    line-height: 1.2;
    order: 1;
    padding: 0.2rem 0.45rem;
    white-space: nowrap;
  }
`;

const onlineCardPreviewStyle = `
  .online-scene-card-preview-wrap {
    height: 100%;
    position: relative;
    width: 100%;
  }

  .online-scene-card-hover-preview {
    background: #000;
    inset: 0;
    opacity: 0;
    overflow: hidden;
    pointer-events: none;
    position: absolute;
    transition: opacity 140ms ease-in-out;
    z-index: 1;
  }

  .online-scene-card-preview-wrap:hover .online-scene-card-hover-preview--active,
  .online-scene-card-hover-preview--active {
    opacity: 1;
  }

  .online-scene-card-hover-preview .video-js,
  .online-scene-card-hover-preview video {
    height: 100%;
    inset: 0;
    object-fit: cover;
    position: absolute;
    width: 100%;
  }

  .online-scene-card-hover-preview .vjs-control-bar,
  .online-scene-card-hover-preview .vjs-big-play-button,
  .online-scene-card-hover-preview .vjs-loading-spinner,
  .online-scene-card-hover-preview .vjs-modal-dialog {
    display: none;
  }
`;

const OnlineSceneCardDurationOverlay: React.FC<{ sceneID: string }> = ({ sceneID }) => {
  const { data } = useQuery<IOnlineDurationData, IOnlineMediaVariables>(
    FIND_SCENE_ONLINE_DURATION,
    {
      variables: { id: sceneID },
      fetchPolicy: "cache-first",
    }
  );

  const durationSeconds = data?.findScene?.online_media?.duration_seconds;

  if (!durationSeconds || durationSeconds <= 0) {
    return null;
  }

  return (
    <div className="scene-specs-overlay">
      <span className="overlay-duration">
        {TextUtils.secondsToTimestamp(durationSeconds)}
      </span>
    </div>
  );
};

const OnlineSceneCardHoverPreview: React.FC<{
  active: boolean;
  sceneID: string;
}> = ({ active, sceneID }) => {
  const videoEl = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<ReturnType<typeof videojs> | null>(null);
  const hoverTimerRef = useRef<number>();
  const { data } = useQuery<IOnlinePreviewData, IOnlineMediaVariables>(
    FIND_SCENE_ONLINE_PREVIEW,
    {
      variables: { id: sceneID },
      fetchPolicy: "cache-first",
    }
  );

  const media = data?.findScene?.online_media;
  const directVideoURL = media?.direct_video_url;

  useEffect(() => {
    return () => {
      window.clearTimeout(hoverTimerRef.current);

      const player = playerRef.current;
      if (player && !player.isDisposed()) {
        player.dispose();
      }
    };
  }, []);

  useEffect(() => {
    if (!active || !directVideoURL || !videoEl.current) {
      window.clearTimeout(hoverTimerRef.current);

      const player = playerRef.current;
      if (player && !player.isDisposed()) {
        player.pause();
        player.currentTime(0);
      }

      return;
    }

    hoverTimerRef.current = window.setTimeout(() => {
      if (!videoEl.current) return;

      const player =
        playerRef.current && !playerRef.current.isDisposed()
          ? playerRef.current
          : videojs(videoEl.current, {
              autoplay: false,
              controls: false,
              loop: true,
              muted: true,
              preload: "none",
            });

      playerRef.current = player;
      player.muted(true);
      player.src({
        src: directVideoURL,
        type: isHLSURL(directVideoURL) ? "application/x-mpegURL" : "video/mp4",
      });

      const playPromise = player.play();
      if (playPromise) {
        playPromise.catch(() => {});
      }
    }, 350);

    return () => {
      window.clearTimeout(hoverTimerRef.current);
    };
  }, [active, directVideoURL]);

  if (!directVideoURL) {
    return null;
  }

  return (
    <div
      className={`online-scene-card-hover-preview${
        active ? " online-scene-card-hover-preview--active" : ""
      }`}
    >
      <style>{onlineCardPreviewStyle}</style>
      <video
        ref={videoEl}
        className="video-js scene-card-preview-video"
        disableRemotePlayback
        loop
        muted
        playsInline
        poster={media?.thumbnail_url ?? undefined}
        preload="none"
      />
    </div>
  );
};

const OnlineSceneCardImagePatch: React.FC<{
  props: ISceneCardImagePatchProps;
  ret: React.ReactNode;
}> = ({ props, ret }) => {
  const [active, setActive] = useState(false);

  if (props.scene.files.length > 0 || props.selecting) {
    return <>{ret}</>;
  }

  return (
    <div
      className="online-scene-card-preview-wrap"
      onMouseEnter={() => setActive(true)}
      onMouseLeave={() => setActive(false)}
    >
      <style>{onlineCardPreviewStyle}</style>
      {ret}
      <OnlineSceneCardHoverPreview active={active} sceneID={props.scene.id} />
    </div>
  );
};

const OnlineScenePlayer: React.FC<{ sceneID: string }> = ({ sceneID }) => {
  const { data, loading, error } = useQuery<IOnlineMediaData, IOnlineMediaVariables>(
    FIND_SCENE_ONLINE_MEDIA,
    {
      variables: { id: sceneID },
      fetchPolicy: "cache-and-network",
    }
  );

  const media = data?.findScene?.online_media ?? null;
  const streams = useMemo(() => (media ? buildPlaybackStreams(media) : []), [media]);
  const primaryStream = useMemo(
    () => streams.find((stream) => stream.is_primary) ?? streams[0],
    [streams]
  );
  const [selectedURL, setSelectedURL] = useState<string>();

  useEffect(() => {
    setSelectedURL(primaryStream?.url);
  }, [primaryStream?.url]);

  if (loading && !media) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorMessage error={error.message} />;
  }

  if (!media) {
    return (
      <Alert variant="warning" className="m-3">
        No local files or online media are available for this scene.
      </Alert>
    );
  }

  const selectedStream =
    streams.find((stream) => stream.url === selectedURL) ?? primaryStream;
  const sourceURL = media.page_url || media.canonical_url || selectedStream?.url;

  return (
    <div className="online-scene-player h-100">
      <style>{onlinePlayerStyle}</style>

      <div className="online-scene-player__frame h-100 bg-black">
        {selectedStream && isDirectStream(selectedStream) ? (
          <video
            key={selectedStream.url}
            className="w-100 h-100"
            src={selectedStream.url}
            controls
            autoPlay={false}
            playsInline
          />
        ) : selectedStream ? (
          <iframe
            key={selectedStream.url}
            title="Online scene player"
            src={selectedStream.url}
            className="w-100 h-100 border-0"
            allow="autoplay; encrypted-media; picture-in-picture"
            allowFullScreen
          />
        ) : (
          <Alert variant="warning">No playable online stream was found.</Alert>
        )}

        <div className="online-scene-player__controls">
          {streams.length > 1 && (
            <Form.Control
              aria-label="Online media server"
              as="select"
              className="online-scene-player__server"
              size="sm"
              value={selectedStream?.url ?? ""}
              onChange={(e) => setSelectedURL(e.target.value)}
            >
              {streams.map((stream) => (
                <option key={stream.url} value={stream.url}>
                  {stream.label || `Server ${stream.position + 1}`}
                  {stream.kind === "direct" ? " · direct" : ""}
                </option>
              ))}
            </Form.Control>
          )}

          {!!sourceURL && (
            <Button
              className="online-scene-player__source-button"
              size="sm"
              variant="outline-secondary"
              href={sourceURL}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open source
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

instead(
  "ScenePlayer",
  (props: IScenePlayerPatchProps, next: React.FC<IScenePlayerPatchProps>) => {
    if (props.scene.files.length === 0) {
      return <OnlineScenePlayer sceneID={props.scene.id} />;
    }

    return next(props);
  }
);

instead(
  "SceneCard.SceneSpecs",
  (
    props: ISceneCardSceneSpecsPatchProps,
    next: React.FC<ISceneCardSceneSpecsPatchProps>
  ) => {
    if (props.scene.files.length === 0) {
      return <OnlineSceneCardDurationOverlay sceneID={props.scene.id} />;
    }

    return next(props);
  }
);

after("SceneCard.Image", (...args: unknown[]) => {
  const props = args[0] as ISceneCardImagePatchProps;
  const ret = args[args.length - 1] as React.ReactNode;

  return <OnlineSceneCardImagePatch props={props} ret={ret} />;
});

export default OnlineScenePlayer;
