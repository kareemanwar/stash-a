import React, { useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  Dropdown,
  Form,
  InputGroup,
  Row,
} from "react-bootstrap";
import { faPlayCircle } from "@fortawesome/free-solid-svg-icons";
import { Icon } from "src/components/Shared/Icon";

type ScraperTestOption = {
  id: string;
  label: string;
  description: string;
};

const scraperTestOptions: ScraperTestOption[] = [
  {
    id: "arabgy-scene-url",
    label: "Arabgy scene URL",
    description: "Planned test profile for Arabgy scene URL output.",
  },
  {
    id: "generic-scene-url",
    label: "Generic scene URL",
    description: "Generic scene URL test profile for future scraper work.",
  },
  {
    id: "performer-url",
    label: "Performer URL",
    description: "Placeholder for performer URL scraper tests.",
  },
  {
    id: "image-gallery-url",
    label: "Image/Gallery URL",
    description: "Placeholder for image and gallery URL scraper tests.",
  },
];

export const ScraperTest: React.FC = () => {
  const [input, setInput] = useState("");
  const [selectedOptionID, setSelectedOptionID] = useState(
    scraperTestOptions[0].id
  );
  const [output, setOutput] = useState("");

  const selectedOption = useMemo(() => {
    return (
      scraperTestOptions.find((option) => option.id === selectedOptionID) ??
      scraperTestOptions[0]
    );
  }, [selectedOptionID]);

  function onRunTest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setOutput(
      JSON.stringify(
        {
          status: "ready",
          scraper_test: selectedOption,
          input,
          note:
            "Scraper execution is not wired yet. This tab is UI infrastructure for future scraper development.",
        },
        null,
        2
      )
    );
  }

  return (
    <div className="mt-4">
      <Row>
        <Col lg={8} xl={7}>
          <Card>
            <Card.Header>
              <h4 className="mb-0">Scraper Test</h4>
            </Card.Header>
            <Card.Body>
              <p className="text-muted">
                Developer workspace for testing scraper output. This first version
                only provides the native UI shell: input, scraper selector, run
                button, and output panel.
              </p>

              <Form onSubmit={onRunTest}>
                <Form.Group controlId="scraper-test-input">
                  <Form.Label>Input URL or test text</Form.Label>
                  <InputGroup>
                    <Form.Control
                      type="text"
                      value={input}
                      onChange={(event) => setInput(event.currentTarget.value)}
                      placeholder="Paste a URL or test input"
                    />
                    <Dropdown as={InputGroup.Append}>
                      <Dropdown.Toggle variant="secondary">
                        {selectedOption.label}
                      </Dropdown.Toggle>
                      <Dropdown.Menu>
                        {scraperTestOptions.map((option) => (
                          <Dropdown.Item
                            key={option.id}
                            active={option.id === selectedOptionID}
                            onClick={() => setSelectedOptionID(option.id)}
                          >
                            {option.label}
                          </Dropdown.Item>
                        ))}
                      </Dropdown.Menu>
                    </Dropdown>
                  </InputGroup>
                  <Form.Text muted>{selectedOption.description}</Form.Text>
                </Form.Group>

                <Button type="submit" variant="primary">
                  <Icon icon={faPlayCircle} /> Run Test
                </Button>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={4} xl={5}>
          <Card>
            <Card.Header>
              <h5 className="mb-0">Output</h5>
            </Card.Header>
            <Card.Body>
              <Form.Control
                as="textarea"
                rows={18}
                readOnly
                value={output}
                placeholder="Test output will appear here."
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ScraperTest;
