# Gherkin Syntax Reference

The `behave` framework uses Gherkin syntax to define features and scenarios. These are stored in `.feature` files.

## Basic Structure

```gherkin
Feature: Short, descriptive title of the feature
  As a [role]
  I want [feature]
  So that [benefit]

  # This is a comment

  Background:
    Given some precondition that applies to all scenarios in this feature

  Scenario: Describe the specific behavior
    Given some initial context
    When an action occurs
    Then an expected outcome should happen
    And another expected outcome
    But an unexpected outcome should not happen

  Scenario Outline: Testing multiple data sets for the same behavior
    Given there are <start> cucumbers
    When I eat <eat> cucumbers
    Then I should have <left> cucumbers

    Examples:
      | start | eat | left |
      |  12   |  5  |  7   |
      |  20   |  5  |  15  |
```

## Keywords
- **Feature**: The name of the feature being tested.
- **Background**: Steps executed before every Scenario in the file.
- **Scenario**: A specific test case.
- **Scenario Outline**: A template for a Scenario that is run once for each row in the `Examples` table.
- **Given**: Sets up the initial state or context.
- **When**: Describes an action or event.
- **Then**: Describes the expected outcome or assertion.
- **And** / **But**: Used to chain multiple Given, When, or Then steps for readability.

## Best Practices
- Keep scenarios focused on one behavior.
- Use Scenario Outlines for repetitive edge cases.
- Avoid implementation details in Gherkin (e.g., "When I click the login button" -> "When I log in").
