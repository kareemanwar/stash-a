import React from "react";
import { Alert } from "react-bootstrap";
import { instead } from "src/patch";

interface IScenePlayerPatchProps {
  scene: {
    id: string;
    files: unknown[];
  };
}

const OnlineScenePlayer: React.FC<{ sceneID: string }> = ({ sceneID }) => {
  return <Alert variant="info">Online scene player: {sceneID}</Alert>;
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
