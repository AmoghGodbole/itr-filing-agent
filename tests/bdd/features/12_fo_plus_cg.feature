Feature: F&O income combined with capital gains

  Scenario: F&O presence forces ITR-3 even when capital gains present
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And equity capital gains with post-Jul-23 STCG of 200000
    And F&O data with one segment gross profit 100000 and gross loss 0 and expenses 0
    When the tax engine computes both regimes
    Then the ITR form selected should be ITR-3
    And is_itr2 should be False

  Scenario: Both F&O income and CG tax appear in computation
    Given a Form 16 with gross salary 1000000 and TDS 60000
    And equity capital gains with post-Jul-23 LTCG of 300000
    And F&O data with one segment gross profit 200000 and gross loss 0 and expenses 0
    When the tax engine computes both regimes
    Then the taxable F&O income should be 200000
    And the capital gains tax at special rates should be 21875
    And the ITR form selected should be ITR-3
