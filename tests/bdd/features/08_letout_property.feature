Feature: Let-out property rental income

  Scenario: HP income computed correctly from rent minus expenses
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And a let-out property with annual rent 360000 municipal taxes 12000 and loan interest 100000
    When the tax engine computes both regimes
    # AV = 360k - 12k = 348k; Sec 24a = 30% of 348k = 104.4k; net AV = 243.6k; less interest 100k = 143.6k
    Then the HP income should be 143600

  Scenario: HP loss capped at 200000 for same-year set-off
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And a let-out property with annual rent 360000 municipal taxes 12000 and loan interest 500000
    When the tax engine computes both regimes
    Then the HP income should be -200000

  Scenario: Let-out property disables self-occupied home loan deduction
    Given a Form 16 with gross salary 1200000 and home loan interest 24b of 150000
    And a let-out property with annual rent 360000 municipal taxes 0 and loan interest 0
    When the tax engine computes both regimes
    Then the old regime home loan interest claimed should be 0
