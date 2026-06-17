import React, { useEffect, useMemo, useState } from "react";
import { gql, useQuery } from "@apollo/client";
import { Alert, Button, Form } from "react-bootstrap";
import { ErrorMessage } from "src/components/Shared/ErrorMessage";
import { LoadingIndicator } from "src/components/Shared/LoadingIndicator";
import { instead } from "src/patch";
import TextUtils from "src/utils/text";

interface IScenePlayerPatchProps {
  scene: {
    id: string;
    files: unknown[];
  };
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

function isDirectStream(stream: IOnlineStream) {
  return (
    stream.kind === "direct" || /\.(?:mp4|m3u8)(?:$|[?#])/i.test(stream.url)
  );
}

function buildPlaybackStreams(media: IOnlineMedia): IOnlineStream[] {
  const streams = [...(media.streams ?? [])].sort((a, b) => a.position - b.position);
  const seen = new Set(streams.map((stream) => stream.url));

  if (media.direct_video_url && !seen.has(media.direct_video_url)) {
    streams.unshift({
      label: "Direct video",
      kind: "direct",
      url: media.direct_video_url,
      position: -2,
      is_primary: streams.length === 0,
    });
    seen.add(media.direct_video_url);
  }

  if (media.embed_url && !seen.has(media.embed_url)) {
    streams.unshift({
      label: "Primary embed",
      kind: "embed",
      url: media.embed_url,
      position: -1,
      is_primary: streams.length === 0,
    });
  }

  return streams;
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

export default OnlineScenePlayer;
