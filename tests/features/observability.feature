Feature: Observability of every request
  Support staff can answer what happened to request X using the id, the JSON
  log and the metrics of the process.

  Scenario: The id sent by the client is reused
    Given the observed assistant is running
    When the user asks "¿Quién es EMP-0004?" with the request id "demo-123"
    Then the X-Request-ID header is "demo-123"
    And the response body request_id is "demo-123"

  Scenario: Every endpoint and every error returns a generated id
    Given the observed assistant is running
    When the client requests each of "/", "/health", "/metrics" and "/missing"
    Then every response has a generated X-Request-ID header

  Scenario: Each request writes one request event
    Given the observed assistant is running with a fixed clock
    When the client requests "/health"
    Then the log has one "request" event with method "GET", path "/health" and status 200
    And every log line has ts in UTC, service "hr-assistant", event and request_id
    And the request event has latency_ms 0

  Scenario: The agent run and its tool calls are audited without user text
    Given the observed assistant is running
    When the user asks "¿Quién es EMP-0004?" with the request id "demo-123"
    Then the log has an "agent_run" event with 2 steps and tools "get_employee"
    And the log has an "audit" event with action "tool_call" and tool "get_employee"
    And no log line contains the question text
    And no log line contains the answer text

  Scenario: An unexpected failure returns a controlled 500
    Given the observed assistant is running with a failing model
    When the user asks "¿Quién es EMP-0004?" with the request id "demo-500"
    Then the response status is 500
    And the response body is "internal error" with request_id "demo-500"
    And the log has an "error" event with the type "RuntimeError"
    And no log line contains the failure message

  Scenario: The metrics report this process
    Given the observed assistant is running
    When the user asks "¿Quién es EMP-0004?"
    And the client requests "/metrics"
    Then the metrics have the documented shape
    And the SLO is met

  Scenario: The SLO is not met when requests are slower than the target
    Given the observed assistant is running with a slow clock and a target of 2000 ms
    When the user asks "¿Quién es EMP-0004?"
    And the client requests "/metrics"
    Then the SLO is not met

  Scenario: Without a LangSmith key the product works and does not connect
    Given the observed assistant is running without a LangSmith key
    And any network connection is forbidden
    When the user asks "¿Quién es EMP-0004?"
    Then the response status is 200
