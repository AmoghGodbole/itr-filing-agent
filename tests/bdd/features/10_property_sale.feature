Feature: Property sale capital gains (manual entry)

  Scenario: Property STCG added to slab income
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And property capital gains with STCG of 200000
    When the tax engine computes both regimes
    Then the ITR form selected should be ITR-2
    And the old regime taxable income should include the property STCG

  Scenario: Property LTCG with indexation taxed at 20 percent
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And property capital gains with LTCG with indexation of 500000
    When the tax engine computes both regimes
    Then the capital gains tax at special rates should be 100000

  Scenario: Property LTCG both indexation options rejected
    Given a PropertyGains model with LTCG with indexation 300000 and LTCG without indexation 200000
    Then creating the PropertyGains should raise a ValidationError
