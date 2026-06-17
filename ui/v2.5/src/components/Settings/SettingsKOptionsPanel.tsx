import React from "react";
import { Form } from "react-bootstrap";
import { SettingSection } from "./SettingSection";
import { useSettings } from "./context";

export const SettingsKOptionsPanel: React.FC = () => {
  const { ui, saveUI } = useSettings();

  const kOptions = ui.kOptions ?? {};
  const showTestTab = kOptions.showScraperTestTab ?? true;
  const enableOnlineScenes = kOptions.enableOnlineScenes ?? true;

  function saveKOptions(next: typeof kOptions) {
    saveUI({
      kOptions: {
        ...kOptions,
        ...next,
      },
    });
  }

  return (
    <SettingSection id="k-options">
      <h1>K-Options</h1>
      <div className="sub-heading">Stash-a feature switches.</div>

      <div className="setting-section" id="k-options-test-tab">
        <div className="setting">
          <div>
            <h3>Test tab</h3>
            <div className="sub-heading">
              Show the Test tab in the top navigation.
            </div>
          </div>
          <Form.Check
            id="k-options-show-test-tab"
            type="switch"
            checked={showTestTab}
            onChange={(event) =>
              saveKOptions({ showScraperTestTab: event.currentTarget.checked })
            }
          />
        </div>
      </div>

      <div className="setting-section" id="k-options-online-scenes">
        <div className="setting">
          <div>
            <h3>Online scenes</h3>
            <div className="sub-heading">
              Enable online scene imports and playback experiments.
            </div>
          </div>
          <Form.Check
            id="k-options-enable-online-scenes"
            type="switch"
            checked={enableOnlineScenes}
            onChange={(event) =>
              saveKOptions({ enableOnlineScenes: event.currentTarget.checked })
            }
          />
        </div>
      </div>
    </SettingSection>
  );
};

export default SettingsKOptionsPanel;
