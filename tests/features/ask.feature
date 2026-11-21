Feature: Ask the HR assistant about employees
  HR staff ask questions and the single agent answers using read-only tools.

  Background:
    Given the assistant is running with the demo directory

  Scenario: Ask for an existing employee
    When the user asks "¿Quién es EMP-0004?"
    Then the response status is 200
    And the answer mentions "Jorge Díaz"
    And the tools used are "get_employee"
    And the agent took 2 steps

  Scenario: Ask for an employee that does not exist
    When the user asks "¿Quién es EMP-9999?"
    Then the response status is 200
    And the answer mentions "EMP-9999"
    And the answer does not mention "Jorge Díaz"

  Scenario: Ask for the people of a department
    When the user asks "¿Quiénes trabajan en Finanzas?"
    Then the answer mentions "Sofía Gómez"
    And the tools used are "search_by_department"

  Scenario: Ask something without an id or a department
    When the user asks "Hola"
    Then the answer mentions "Pregúntame por un empleado"
    And no tools were used

  Scenario: The step limit stops the loop
    Given the assistant is running with a limit of 1 step
    When the user asks "¿Quién es EMP-0004?"
    Then the answer is the step limit message
    And the agent took 1 steps

  Scenario: An empty question is rejected
    When the user asks ""
    Then the response status is 422

  Scenario: A question that is too long is rejected
    Given the assistant is running with a limit of 50 characters
    When the user asks a question of 51 characters
    Then the response status is 422
