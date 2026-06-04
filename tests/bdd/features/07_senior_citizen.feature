Feature: Senior citizen and super senior citizen slabs

  Scenario: Senior citizen gets higher basic exemption and 80TTB
    Given a Form 16 with gross salary 800000 and TDS 30000
    And AIS data with FD interest 60000 and savings interest 5000
    And date of birth 01/06/1960 with assessment year AY 2025-26
    When the tax engine computes both regimes
    Then the taxpayer should be classified as a senior citizen
    And the old regime 80TTB deduction should be 50000
    And the old regime 80TTA deduction should be 0

  Scenario: Super senior citizen gets 500000 basic exemption in old regime
    Given a Form 16 with gross salary 800000 and TDS 20000
    And date of birth 15/03/1944 with assessment year AY 2025-26
    When the tax engine computes both regimes
    Then the taxpayer should be classified as a super senior citizen

  Scenario: Non-senior uses 80TTA not 80TTB
    Given a Form 16 with gross salary 800000 and TDS 30000
    And AIS data with savings interest 15000 and FD interest 40000
    And date of birth 01/01/1985 with assessment year AY 2025-26
    When the tax engine computes both regimes
    Then the old regime 80TTA deduction should be 10000
    And the old regime 80TTB deduction should be 0
