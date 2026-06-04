Feature: F&O income — ITR-3 selection and Schedule BP

  Scenario: F&O profit triggers ITR-3 and adds to slab income
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And F&O data with one segment gross profit 300000 and gross loss 100000 and expenses 20000
    When the tax engine computes both regimes
    Then the ITR form selected should be ITR-3
    And the taxable F&O income should be 180000

  Scenario: F&O loss does not reduce salary income
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And F&O data with one segment gross profit 50000 and gross loss 200000 and expenses 0
    When the tax engine computes both regimes
    Then the taxable F&O income should be 0
    And the current year F&O loss to carry forward should be 150000

  Scenario: Prior year loss set off capped at current net income
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And F&O data with one segment gross profit 200000 and gross loss 100000 and expenses 0
    And prior year F&O losses of 500000 from AY 2024-25
    When the tax engine computes both regimes
    Then the prior year loss set off should be 100000
    And the taxable F&O income should be 0

  Scenario: Tax audit required when turnover exceeds 10 crore
    Given F&O data with turnover 120000000
    Then the F&O data should require tax audit

  Scenario: Tax audit required when loss declared at any turnover
    Given F&O data with one segment gross profit 50000 and gross loss 200000 and expenses 0
    Then the F&O data should require tax audit
