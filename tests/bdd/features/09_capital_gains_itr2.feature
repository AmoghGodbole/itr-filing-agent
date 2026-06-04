Feature: Capital gains — ITR-2 selection and tax computation

  Scenario: Equity STCG triggers ITR-2 and taxed at correct rate
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And equity capital gains with post-Jul-23 STCG of 200000
    When the tax engine computes both regimes
    Then the ITR form selected should be ITR-2
    And the capital gains tax at special rates should be 40000

  Scenario: Equity LTCG post-Jul-23 applies 125000 exemption
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And equity capital gains with post-Jul-23 LTCG of 300000
    When the tax engine computes both regimes
    Then the ITR form selected should be ITR-2
    And the taxable LTCG post-Jul-23 should be 175000
    And the capital gains tax at special rates should be 21875

  Scenario: Pre-Jul-23 LTCG uses 100000 exemption at 10 percent
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And equity capital gains with pre-Jul-23 LTCG of 250000
    When the tax engine computes both regimes
    Then the taxable LTCG pre-Jul-23 should be 150000
    And the capital gains tax at special rates should be 15000

  Scenario: 87A rebate not available when slab+CG total exceeds 7L in new regime
    Given a Form 16 with gross salary 600000 and TDS 0
    And equity capital gains with post-Jul-23 STCG of 200000
    When the tax engine computes both regimes
    # slab income = 600k - 75k std = 525k; total = 525k + 200k STCG = 725k > 700k threshold
    Then the new regime 87A rebate should be 0
