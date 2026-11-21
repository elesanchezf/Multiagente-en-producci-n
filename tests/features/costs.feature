Feature: Cheaper answers through routing and cost reporting
  Each answer reports the model used and what it cost, and the cost levers
  can be turned on and off by configuration.

  Scenario: A simple question goes to the small model
    Given the assistant is running with the default cost levers
    When the user asks "¿Quién es EMP-0004?"
    Then the response status is 200
    And the model used is the small model
    And the route reason is not empty

  Scenario: A question with a keyword goes to the large model
    Given the assistant is running with the default cost levers
    When the user asks "Compara a los empleados de Finanzas"
    Then the model used is the large model
    And the route reason is not empty

  Scenario: Routing disabled sends every question to the large model
    Given the assistant is running with routing disabled
    When the user asks "¿Quién es EMP-0004?"
    Then the model used is the large model

  Scenario: The cost of an answer is reported and added to the metrics
    Given the assistant is running with the default cost levers
    When the user asks "¿Quién es EMP-0004?"
    Then the cost matches the tokens and the price of the model used
    And the answer reports 0 cached calls
    And the metrics cost equals the cost of the answer

  Scenario: A model failure returns a controlled error
    Given the assistant is running with a model that always fails
    When the user asks "¿Quién es EMP-0004?"
    Then the response status is 502
    And the error detail is "model unavailable"
    And the error carries the request id of the response

  Scenario: The gateway provider does not start without credentials
    When the service starts with the gateway provider and no Cloudflare variables
    Then the start fails naming the variable "CF_ACCOUNT_ID"
