import React, { useState } from "react";
import { Button, Card, Col, Form, Row } from "react-bootstrap";

const contentTypes = ["Scene", "Performer", "Image", "Gallery"];

export const ScraperTest: React.FC = () => {
  const [url, setURL] = useState("");
  const [contentType, setContentType] = useState(contentTypes[0]);

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
                Developer workspace for wiring and testing native scraper output.
                No provider-specific scraper is hardcoded here.
              </p>

              <Form>
                <Form.Group controlId="scraper-test-url">
                  <Form.Label>URL</Form.Label>
                  <Form.Control
                    type="text"
                    value={url}
                    onChange={(event) => setURL(event.currentTarget.value)}
                    placeholder="Paste a URL to test"
                  />
                </Form.Group>

                <Form.Group controlId="scraper-test-content-type">
                  <Form.Label>Content type</Form.Label>
                  <Form.Control
                    as="select"
                    value={contentType}
                    onChange={(event) =>
                      setContentType(event.currentTarget.value)
                    }
                  >
                    {contentTypes.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </Form.Control>
                </Form.Group>

                <Button type="button" variant="primary" disabled>
                  Test
                </Button>
                <Form.Text muted className="d-block mt-2">
                  Scraper execution is not wired yet.
                </Form.Text>
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
                value=""
                placeholder="Scraper output will appear here."
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ScraperTest;
