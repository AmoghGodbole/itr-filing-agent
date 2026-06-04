Feature: Basic salaried employee ITR-1

  Scenario: Single employer with standard deductions — new regime recommended
    Given a Form 16 with gross salary 1200000 and TDS 85000
    And 80C deductions of 150000 and 80D self of 15000
    When the tax engine computes both regimes
    Then the ITR form selected should be ITR-1
    And the recommended regime should be New Regime
    And the new regime taxable income should be 1125000
    And the new regime tax payable should be 71500

  Scenario: Standard deduction applied correctly in both regimes
    Given a Form 16 with gross salary 800000 and TDS 30000
    When the tax engine computes both regimes
    Then the old regime taxable income should account for standard deduction of 50000
    And the new regime taxable income should account for standard deduction of 75000
