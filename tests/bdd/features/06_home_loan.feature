Feature: Home loan interest deduction (self-occupied property)

  Scenario: Home loan interest from Form 16 claimed as deduction
    Given a Form 16 with gross salary 1200000 and home loan interest 24b of 180000
    When the tax engine computes both regimes
    # For self-occupied: hp_income=0, interest is a deduction
    Then the old regime home loan interest claimed should be 180000
    And the new regime home loan interest claimed should be 0

  Scenario: Bank certificate overrides Form 16 home loan figure
    Given a Form 16 with gross salary 1200000 and home loan interest 24b of 100000
    And a bank certificate home loan interest of 220000
    When the tax engine computes both regimes
    Then the old regime home loan interest claimed should be 200000

  Scenario: Home loan interest capped at 200000
    Given a Form 16 with gross salary 1500000 and home loan interest 24b of 300000
    When the tax engine computes both regimes
    Then the old regime home loan interest claimed should be 200000
