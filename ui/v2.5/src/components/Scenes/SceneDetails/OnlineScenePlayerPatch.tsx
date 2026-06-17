import React, { useEffect, useMemo, useState } from "react";
import { gql, useQuery } from "@apollo/client";
import { Alert, Badge, Button, Form } from "react-bootstrap";
import { ErrorMessage } from "src/components/Shared/ErrorMessage";
import { LoadingIndicator } from "src/components/Shared/LoadingIndicator";
import { instead } from "src/patch";

interface IScenePlayerPatchProps {
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
    <div className="online-scene-player h-100 d-flex flex-column p-3">
      <div className="d-flex align-items-center justify-content-between mb-2">
        <div className="d-flex align-items-center">
          <Badge variant="success" className="mr-2">
            Online
          </Badge>
          <span className="text-muted small">
            {media.source_name}
            {media.external_view_count != null
              ? ` · ${media.external_view_count} views`
              : ""}
          </span>
        </div>
        {!!sourceURL && (
          <Button
            size="sm"
            variant="secondary"
            href={sourceURL}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open source
          </Button>
        )}
      </div>

      {streams.length > 1 && (
        <Form.Group controlId="online-scene-server" className="mb-2">
          <Form.Label className="small text-muted mb-1">Server</Form.Label>
          <Form.Control
            as="select"
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
        </Form.Group>
      )}

      <div className="online-scene-player__frame flex-grow-1 bg-black">
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
      </div>

      {!!sourceURL && (
        <div className="mt-2">
          <Button
            size="sm"
            variant="outline-secondary"
            href={sourceURL}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open source
          </Button>
        </div>
      )}
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

export default OnlineScenePlayer;
