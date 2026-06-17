import React from "react";
import { gql, useQuery } from "@apollo/client";
import { Alert, Badge, Nav, Tab, Table } from "react-bootstrap";
import { ErrorMessage } from "src/components/Shared/ErrorMessage";
import { LoadingIndicator } from "src/components/Shared/LoadingIndicator";
import { after } from "src/patch";
import TextUtils from "src/utils/text";

interface IScenePagePatchProps {
  scene: {
    id: string;
    files: unknown[];
  };
}

interface ISceneCardDetailsPatchProps {
  scene: {
    id: string;
    files: unknown[];
  };
}

interface IOnlineStream {
  id: string;
  label?: string | null;
  kind: string;
  url: string;
  position: number;
  is_primary: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

interface IOnlineMedia {
  id: string;
  scene_id: string;
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
  raw_metadata_json?: string | null;
  last_scraped_at?: string | null;
  created_at: string;
  updated_at: string;
  streams: IOnlineStream[];
}

interface IOnlineMediaData {
  findScene?: {
    id: string;
    online_media?: IOnlineMedia | null;
  } | null;
}

interface IOnlineViewsData {
  findScene?: {
    id: string;
    online_media?: {
      external_view_count?: number | null;
    } | null;
  } | null;
}

const FIND_SCENE_ONLINE_METADATA = gql`
  query FindSceneOnlineMetadata($id: ID!) {
    findScene(id: $id) {
      id
      online_media {
        id
        scene_id
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
        raw_metadata_json
        last_scraped_at
        created_at
        updated_at
        streams {
          id
          label
          kind
          url
          position
          is_primary
          created_at
          updated_at
        }
      }
    }
  }
`;

const FIND_SCENE_ONLINE_VIEWS = gql`
  query FindSceneOnlineViews($id: ID!) {
    findScene(id: $id) {
      id
      online_media {
        external_view_count
      }
    }
  }
`;

function formatDuration(seconds?: number | null) {
  return seconds && seconds > 0 ? TextUtils.secondsToTimestamp(seconds) : undefined;
}

function formatViews(count?: number | null) {
  if (count == null) return undefined;
  return `${count.toLocaleString()} views`;
}

function prettyJSON(input?: string | null) {
  if (!input) return undefined;

  try {
    return JSON.stringify(JSON.parse(input), null, 2);
  } catch (_e) {
    return input;
  }
}

const MetadataValue: React.FC<{ value?: React.ReactNode; href?: string | null }> = ({
  value,
  href,
}) => {
  if (value == null || value === "") {
    return <span className="text-muted">—</span>;
  }

  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {value}
      </a>
    );
  }

  return <>{value}</>;
};

const MetadataRow: React.FC<{
  label: string;
  value?: React.ReactNode;
  href?: string | null;
}> = ({ label, value, href }) => (
  <tr>
    <th className="text-nowrap pr-3" style={{ width: "11rem" }}>
      {label}
    </th>
    <td style={{ wordBreak: "break-word" }}>
      <MetadataValue value={value} href={href} />
    </td>
  </tr>
);

const OnlineScenePanel: React.FC<{ sceneID: string }> = ({ sceneID }) => {
  const { data, loading, error } = useQuery<IOnlineMediaData, { id: string }>(
    FIND_SCENE_ONLINE_METADATA,
    {
      variables: { id: sceneID },
      fetchPolicy: "cache-and-network",
    }
  );

  if (loading && !data?.findScene?.online_media) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorMessage error={error.message} />;
  }

  const media = data?.findScene?.online_media;
  if (!media) {
    return (
      <Alert variant="warning" className="m-3">
        No online media is stored for this scene.
      </Alert>
    );
  }

  const streams = [...(media.streams ?? [])].sort(
    (a, b) => a.position - b.position
  );
  const rawMetadata = prettyJSON(media.raw_metadata_json);

  return (
    <div className="scene-online-panel p-3">
      <h5>Online media</h5>
      <div className="table-responsive">
        <Table size="sm" borderless>
          <tbody>
            <MetadataRow
              label="Source"
              value={`${media.source_name} (${media.source_slug})`}
            />
            <MetadataRow label="External ID" value={media.external_id} />
            <MetadataRow
              label="Duration"
              value={formatDuration(media.duration_seconds)}
            />
            <MetadataRow
              label="Views"
              value={formatViews(media.external_view_count)}
            />
            <MetadataRow
              label="Page URL"
              value={media.page_url}
              href={media.page_url}
            />
            <MetadataRow
              label="Canonical URL"
              value={media.canonical_url}
              href={media.canonical_url}
            />
            <MetadataRow
              label="Embed URL"
              value={media.embed_url}
              href={media.embed_url}
            />
            <MetadataRow
              label="Direct video URL"
              value={media.direct_video_url}
              href={media.direct_video_url}
            />
            <MetadataRow
              label="Thumbnail URL"
              value={media.thumbnail_url}
              href={media.thumbnail_url}
            />
            <MetadataRow label="Last scraped" value={media.last_scraped_at} />
            <MetadataRow label="Created" value={media.created_at} />
            <MetadataRow label="Updated" value={media.updated_at} />
          </tbody>
        </Table>
      </div>

      <h5 className="mt-4">Streams</h5>
      {streams.length > 0 ? (
        <div className="table-responsive">
          <Table size="sm" striped>
            <thead>
              <tr>
                <th>#</th>
                <th>Label</th>
                <th>Kind</th>
                <th>Primary</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {streams.map((stream) => (
                <tr key={stream.id ?? stream.url}>
                  <td>{stream.position + 1}</td>
                  <td>{stream.label || "—"}</td>
                  <td>{stream.kind}</td>
                  <td>
                    {stream.is_primary ? (
                      <Badge variant="success">Primary</Badge>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td style={{ wordBreak: "break-word" }}>
                    <a href={stream.url} target="_blank" rel="noopener noreferrer">
                      {stream.url}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      ) : (
        <Alert variant="secondary">No online streams are stored.</Alert>
      )}

      {rawMetadata && (
        <details className="mt-4">
          <summary>Raw metadata</summary>
          <pre className="mt-2 p-2 bg-dark" style={{ whiteSpace: "pre-wrap" }}>
            {rawMetadata}
          </pre>
        </details>
      )}
    </div>
  );
};

const OnlineSceneCardViews: React.FC<{ sceneID: string }> = ({ sceneID }) => {
  const { data } = useQuery<IOnlineViewsData, { id: string }>(
    FIND_SCENE_ONLINE_VIEWS,
    {
      variables: { id: sceneID },
      fetchPolicy: "cache-first",
    }
  );

  const views = data?.findScene?.online_media?.external_view_count;
  if (views == null) return null;

  return (
    <div className="scene-card__online-views text-muted small">
      {formatViews(views)}
    </div>
  );
};

function getEventKey(child: React.ReactNode) {
  if (!React.isValidElement(child)) return undefined;

  const childProps = child.props as {
    eventKey?: string;
    children?: React.ReactNode;
  };
  if (childProps.eventKey) return childProps.eventKey;

  for (const nested of React.Children.toArray(childProps.children)) {
    if (!React.isValidElement(nested)) continue;

    const nestedProps = nested.props as { eventKey?: string };
    if (nestedProps.eventKey) return nestedProps.eventKey;
  }

  return undefined;
}

function insertBeforeMarkers(children: React.ReactNode, inserted: React.ReactNode) {
  const childArray = React.Children.toArray(children);
  const markerIndex = childArray.findIndex(
    (child) => getEventKey(child) === "scene-markers-panel"
  );

  if (markerIndex === -1) {
    return [...childArray, inserted];
  }

  return [
    ...childArray.slice(0, markerIndex),
    inserted,
    ...childArray.slice(markerIndex),
  ];
}

function replaceChildren(ret: React.ReactNode, children: React.ReactNode) {
  if (!React.isValidElement(ret)) {
    return <>{children}</>;
  }

  return React.cloneElement(
    ret as React.ReactElement<{ children?: React.ReactNode }>,
    undefined,
    children
  );
}

after("ScenePage.Tabs", (...args: unknown[]) => {
  const props = args[0] as IScenePagePatchProps;
  const ret = args[args.length - 1] as React.ReactNode;

  if (props.scene.files.length > 0) {
    return ret;
  }

  const inserted = (
    <Nav.Item key="scene-online-panel-tab">
      <Nav.Link eventKey="scene-online-panel">Online</Nav.Link>
    </Nav.Item>
  );

  const retProps = React.isValidElement(ret)
    ? (ret.props as { children?: React.ReactNode })
    : undefined;
  const children = retProps?.children ?? ret;
  return replaceChildren(ret, insertBeforeMarkers(children, inserted));
});

after("ScenePage.TabContent", (...args: unknown[]) => {
  const props = args[0] as IScenePagePatchProps;
  const ret = args[args.length - 1] as React.ReactNode;

  if (props.scene.files.length > 0) {
    return ret;
  }

  const inserted = (
    <Tab.Pane eventKey="scene-online-panel" key="scene-online-panel-content">
      <OnlineScenePanel sceneID={props.scene.id} />
    </Tab.Pane>
  );

  const retProps = React.isValidElement(ret)
    ? (ret.props as { children?: React.ReactNode })
    : undefined;
  const children = retProps?.children ?? ret;
  return replaceChildren(ret, insertBeforeMarkers(children, inserted));
});

after("SceneCard.Details", (...args: unknown[]) => {
  const props = args[0] as ISceneCardDetailsPatchProps;
  const ret = args[args.length - 1] as React.ReactNode;

  if (props.scene.files.length > 0 || !React.isValidElement(ret)) {
    return ret;
  }

  const retProps = ret.props as { children?: React.ReactNode };
  return React.cloneElement(
    ret as React.ReactElement<{ children?: React.ReactNode }>,
    undefined,
    <>
      {retProps.children}
      <OnlineSceneCardViews sceneID={props.scene.id} />
    </>
  );
});

export default OnlineScenePanel;
