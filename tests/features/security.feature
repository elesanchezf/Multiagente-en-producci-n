Feature: Safe access in production
  Each client has its own API key and a request limit, and the service refuses
  to start in production when a compliance rule is not met.

  Scenario: Protected routes reject a missing or an invalid key
    Given the secure assistant is running
    When the client calls the protected routes without a key
    Then every response is 401 with the detail "invalid or missing API key"
    When the client calls the protected routes with an invalid key
    Then every response is 401 with the detail "invalid or missing API key"

  Scenario: A valid key is accepted and the public routes need none
    Given the secure assistant is running
    When the client "acme" asks "¿Quién es EMP-0004?"
    Then the response status is 200
    And the public routes "/", "/health" and "/docs" answer 200 without a key

  Scenario: The client name is logged and the key never is
    Given the secure assistant is running
    When the client "acme" asks "¿Quién es EMP-0004?"
    Then the "request", "agent_run" and "audit" log events have the client "acme"
    And no log line contains the key of "acme"

  Scenario: A client over its limit waits while another one is not affected
    Given the secure assistant is running with a limit of 2 requests per minute
    When the client "acme" asks 3 questions
    Then the last response is 429 with the detail "rate limit exceeded"
    And the Retry-After header is a positive number of seconds
    And the client "globex" can still ask a question
    When the clock advances 60 seconds
    Then the client "acme" can still ask a question

  Scenario: Production refuses to start with the fake model
    When the assistant starts in production with the fake model and a valid key
    Then the start is refused and the message names "MODEL_PROVIDER"
    And the message does not contain the key

  Scenario: A malformed key list prevents the start without revealing it
    When the assistant starts with the key list "acme:fake-key-acme-0000000000,broken"
    Then the start is refused and the message gives the length 6 of the failing entry
    And the message does not contain the text "broken"
    And the message does not contain the text "fake-key-acme-0000000000"
