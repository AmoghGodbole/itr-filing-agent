Feature: AIS income — FD interest and dividends

  Scenario: FD interest and dividends added to other sources income
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And AIS data with FD interest 80000 and dividends 20000
    When the tax engine computes both regimes
    Then the other sources income should be 100000
    And the old regime taxable income should include the AIS income

  Scenario: 80TTA savings interest deduction applied for non-senior
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And AIS data with savings interest 15000 and FD interest 0 and dividends 0
    When the tax engine computes both regimes
    Then the old regime 80TTA deduction should be 10000
    And the new regime 80TTA deduction should be 0

  Scenario: 80TTA capped at actual savings interest when below limit
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And AIS data with savings interest 6000 and FD interest 0 and dividends 0
    When the tax engine computes both regimes
    Then the old regime 80TTA deduction should be 6000
