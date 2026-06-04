Feature: Schedule AL — assets and liabilities threshold

  Scenario: Schedule AL included in ITR-2 when total income exceeds 50L
    Given a Form 16 with gross salary 4000000 and TDS 800000
    And equity capital gains with post-Jul-23 LTCG of 1500000
    And schedule AL data with immovable property value 10000000
    When the ITR-2 JSON is generated
    Then the JSON should contain ScheduleAL

  Scenario: Schedule AL omitted when total income below 50L
    Given a Form 16 with gross salary 3000000 and TDS 500000
    And schedule AL data with immovable property value 5000000
    When the ITR-1 JSON is generated
    Then the JSON should not contain ScheduleAL

  Scenario: Special rate CG counts toward Schedule AL threshold
    Given a Form 16 with gross salary 3500000 and TDS 600000
    And equity capital gains with post-Jul-23 LTCG of 2000000
    And schedule AL data with immovable property value 8000000
    When the ITR-2 JSON is generated
    Then the JSON should contain ScheduleAL
