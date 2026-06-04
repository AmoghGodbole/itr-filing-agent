Feature: 80GG rent deduction for employees with no HRA component

  Scenario: 80GG deduction computed when salary has no HRA component
    Given a Form 16 with gross salary 800000 and HRA component 0 and basic 500000
    And the employee pays monthly rent of 15000 in Pune
    When the tax engine computes both regimes
    Then the old regime 80GG deduction claimed should be greater than 0
    And the new regime 80GG deduction claimed should be 0

  Scenario: 80GG is mutually exclusive with HRA exemption
    Given a Form 16 with gross salary 1000000 and HRA component 100000 and basic 500000
    And the employee pays monthly rent of 15000 in Pune
    When the tax engine computes both regimes
    Then the old regime 80GG deduction claimed should be 0
    And the old regime HRA exemption claimed should be greater than 0

  Scenario: 80GG capped at 60000 annual limit
    Given a Form 16 with gross salary 5000000 and HRA component 0 and basic 2500000
    And the employee pays monthly rent of 50000 in Mumbai
    When the tax engine computes both regimes
    Then the old regime 80GG deduction claimed should be 60000
