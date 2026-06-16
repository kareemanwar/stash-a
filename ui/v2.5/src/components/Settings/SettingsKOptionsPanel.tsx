import React from "react";
import { Form } from "react-bootstrap";
import { SettingSection } from "./SettingSection";
import { useSettings } from "./context";

export const SettingsKOptionsPanel: React.FC = () => {
  const { ui, saveUI } = useSettings();

  const kOptions = ui.kOptions ?? {};
  const showTestTab = kOptions.showScraperTestTab ?? true;

  function setShowTestTab(show: boolean) {
    saveUI({
      kOptions: {
        ...kOptions,
        showScraperTestTab: show,
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
            onChange={(event) => setShowTestTab(event.currentTarget.checked)}
          />
        </div>
      </div>
    </SettingSection>
  );
};

export default SettingsKOptionsPanel;
