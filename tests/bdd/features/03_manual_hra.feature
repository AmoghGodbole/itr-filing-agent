Feature: Manual HRA exemption when not declared to employer

  Scenario: Metro city employee claims HRA exemption manually
    Given a Form 16 with gross salary 1200000 and HRA component 120000 and basic 600000
    And the Form 16 shows HRA exemption of 0
    And the employee pays monthly rent of 25000 in Mumbai
    When the tax engine computes both regimes
    # min(HRA=120k, 50% basic=300k, rent 300k - 10% basic 60k=240k) = 120000
    Then the old regime HRA exemption claimed should be 120000
    And the new regime HRA exemption claimed should be 0

  Scenario: Non-metro city reduces HRA percent to 40%
    Given a Form 16 with gross salary 1000000 and HRA component 100000 and basic 500000
    And the Form 16 shows HRA exemption of 0
    And the employee pays monthly rent of 20000 in Pune
    When the tax engine computes both regimes
    # min(HRA=100k, 40% basic=200k, rent 240k - 10% basic 50k=190k) = 100000
    Then the old regime HRA exemption claimed should be 100000

  Scenario: Employer already computed HRA — manual rent input is ignored
    Given a Form 16 with gross salary 1200000 and HRA component 120000 and basic 600000
    And the Form 16 shows HRA exemption of 95000
    And the employee pays monthly rent of 25000 in Mumbai
    When the tax engine computes both regimes
    Then the old regime HRA exemption claimed should be 95000
