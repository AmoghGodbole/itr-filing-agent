Feature: Two Form 16s for job change mid-year

  Scenario: Salaries and TDS merged correctly across two employers
    Given a primary Form 16 with gross salary 700000 and TDS 40000
    And a second Form 16 with gross salary 500000 and TDS 30000
    When the form 16s are merged and tax is computed
    Then the merged gross salary should be 1200000
    And the merged TDS should be 70000
    And the ITR form selected should be ITR-1

  Scenario: PAN mismatch between two Form 16s raises an error
    Given a primary Form 16 with PAN AAAAA0001A
    And a second Form 16 with PAN BBBBB0002B
    Then merging the two Form 16s should raise a ValueError
