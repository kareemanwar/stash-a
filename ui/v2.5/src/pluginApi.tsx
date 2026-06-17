import React from "react";
import ReactDOM from "react-dom";
import * as ReactRouterDOM from "react-router-dom";
import Mousetrap from "mousetrap";
import MousetrapPause from "mousetrap-pause";
import NavUtils from "./utils/navigation";
import * as GQL from "src/core/generated-graphql";
import * as StashService from "src/core/StashService";
import * as Apollo from "@apollo/client";
import * as Bootstrap from "react-bootstrap";
import * as ReactIntl from "react-intl";
import * as FontAwesomeSolid from "@fortawesome/free-solid-svg-icons";
import * as FontAwesomeRegular from "@fortawesome/free-regular-svg-icons";
import * as FontAwesomeBrands from "@fortawesome/free-brands-svg-icons";
import * as ReactFontAwesome from "@fortawesome/react-fontawesome";
import * as ReactSelect from "react-select";
import * as ReactSlick from "@ant-design/react-slick";
import { useSpriteInfo } from "./hooks/sprite";
import { useToast } from "./hooks/Toast";
import Event from "./hooks/event";
import { after, before, components, instead, RegisterComponent } from "./patch";
import { useSettings } from "./components/Settings/context";
import { useInteractive } from "./hooks/Interactive/context";
import InteractiveUtils from "./hooks/Interactive/utils";
import { useLightbox, useGalleryLightbox } from "./hooks/Lightbox/hooks";
import "./components/Scenes/SceneDetails/OnlineScenePlayerPatch";
import "./components/Scenes/SceneDetails/OnlineSceneMetadataPatch";

// due to code splitting, some components may not have been loaded when a plugin
// page is loaded. This function will load all components passed to it.
// The components need to be imported here. Any required imports will be added
// to the loadableComponents object in the plugin api.
async function loadComponents(c: (() => Promise<unknown>)[]) {
  await Promise.all(c.map((fn) => fn()));
}

// useLoadComponents is a hook that loads all components passed to it.
// It returns a boolean indicating whether the components are still loading.
function useLoadComponents(toLoad: (() => Promise<unknown>)[]) {
  const [loading, setLoading] = React.useState(true);
  const [componentList] = React.useState(toLoad);

  React.useEffect(() => {
    async function load(c: (() => Promise<unknown>)[]) {
      await loadComponents(c);
      setLoading(false);
    }

    setLoading(true);
    load(componentList);
  }, [componentList]);

  return loading;
}

function registerRoute(path: string, component: React.FC) {
  before("PluginRoutes", (props: React.PropsWithChildren<unknown>) => {
    return [
      {
        children: (
          <>
            {props.children}
            <ReactRouterDOM.Route path={path} component={component} />
          </>
        ),
      },
    ];
  });
}

export const PluginApi = {
  React,
  ReactDOM,
  GQL,
  libraries: {
    ReactRouterDOM,
    Bootstrap,
    Apollo,
    Intl: ReactIntl,
    FontAwesomeRegular,
    FontAwesomeSolid,
    FontAwesomeBrands,
    ReactFontAwesome,
    ReactSelect,
    Mousetrap,
    MousetrapPause,
    ReactSlick,
  },
  utils: {
    NavUtils,
    InteractiveUtils,
  },
  hooks: {
    useSpriteInfo,
    useToast,
    useSettings,
    useInteractive,
    useLightbox,
    useGalleryLightbox,
    Event,
  },
  patch: {
    before,
    instead,
    after,
    components,
    RegisterComponent,
  },
  loadableComponents: {
    loadComponents,
    useLoadComponents,
  },
  register: {
    route: registerRoute,
  },
};
