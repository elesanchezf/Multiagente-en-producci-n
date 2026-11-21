Feature: Health check and web page
  The service reports its health and serves the page used by HR staff.

  Background:
    Given the assistant is running with the demo directory

  Scenario: The health endpoint reports the process
    When the client requests "/health"
    Then the response status is 200
    And the health status is "ok" and includes a numeric pid

  Scenario: The home page has the question form
    When the client requests "/"
    Then the response status is 200
    And the page has the test ids "question", "send" and "answer"

  Scenario: The home page shows the request id for support
    When the client requests "/"
    Then the page has the test id "request-id"
