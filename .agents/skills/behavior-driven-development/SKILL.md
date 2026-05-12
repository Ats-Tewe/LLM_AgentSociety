---
name: behavior-driven-development
description: Behavior-Driven Development with Given-When-Then scenarios and acceptance criteria
user-invocable: false
---

# Behavior-Driven Development (BDD) Skill

## When to Use

Use this skill when:
- Defining acceptance criteria for features
- Creating executable specifications
- Translating requirements into testable scenarios
- Working with stakeholders on feature definitions
- Part of the unified workflow process

## Overview

BDD bridges the gap between business requirements and technical implementation using natural language scenarios that become executable tests.

## BDD Process

### 1. Discovery Phase

Work with stakeholders to discover scenarios:

**Ask:**
- What is the business value?
- Who are the users/actors?
- What are the main scenarios?
- What can go wrong?
- What edge cases exist?

### 2. Scenario Definition

Write scenarios in Given-When-Then format:

```gherkin
Feature: User Authentication

  Scenario: Successful login with valid credentials
    Given a registered user with email "user@example.com" and password "SecurePass123"
    When the user submits the login form with correct credentials
    Then the user should be redirected to the dashboard
    And the user session should be created
    And the user should see a welcome message

  Scenario: Failed login with invalid password
    Given a registered user with email "user@example.com"
    When the user submits the login form with incorrect password
    Then the user should see an error message "Invalid credentials"
    And the user should remain on the login page
    And no session should be created

  Scenario: Account lockout after multiple failed attempts
    Given a registered user with email "user@example.com"
    And the user has failed to login 4 times
    When the user submits the login form with incorrect password again
    Then the account should be locked for 15 minutes
    And the user should see "Account temporarily locked"
```

### 3. Examples and Data Tables

Use examples for multiple test cases:

```gherkin
  Scenario Outline: Password validation
    Given a user registration form
    When the user enters password "<password>"
    Then the validation should show "<result>"

    Examples:
      | password    | result                          |
      | abc         | Too short (min 8 characters)   |
      | abcdefgh    | Missing uppercase letter       |
      | Abcdefgh    | Missing number                 |
      | Abcdefg1    | Valid                          |
      | Abc123!@#   | Valid                          |
```

### 4. Acceptance Criteria Checklist

For each feature, create acceptance criteria:

```markdown
## Acceptance Criteria

- [ ] User can login with valid email and password
- [ ] Invalid credentials show appropriate error
- [ ] Account locks after 5 failed attempts
- [ ] Locked account shows lockout duration
- [ ] Session expires after 24 hours
- [ ] Logout clears session properly
- [ ] Remember me keeps session for 30 days
```

### 5. Integration with Workflow

**In Spec Phase:**
```
1. Define feature specification (SDD)
2. Write BDD scenarios (this skill)
3. Get stakeholder approval
```

**In Implementation Phase:**
```
1. For each scenario:
   - Write step definitions (glue code)
   - Implement steps using TDD
   - Verify scenario passes
2. Ensure all acceptance criteria met
```

## BDD Scenario Structure

### Given (Context)
- Initial state
- Preconditions
- Setup data
- User context

### When (Action)
- User action
- System event
- API call
- Trigger

### Then (Outcome)
- Expected result
- State changes
- Side effects
- Assertions

### And/But (Additional steps)
- Multiple givens, whens, or thens
- Additional context or assertions

## Best Practices

**DO:**
- Write from user's perspective
- Use business language, not technical jargon
- Focus on behavior, not implementation
- Keep scenarios independent
- Use concrete examples
- Cover happy path and edge cases

**DON'T:**
- Include implementation details
- Make scenarios too long (>5-7 steps)
- Create dependencies between scenarios
- Use vague language
- Test technical details (use unit tests)

## Tools Integration

**Gherkin/Cucumber:**
```bash
# Feature files in features/ directory
features/
├── authentication.feature
├── user_profile.feature
└── payment.feature
```

**Jest/Vitest:**
```javascript
describe('User Authentication', () => {
  it('should login with valid credentials', () => {
    // Given
    const user = createUser({ email: 'user@example.com', password: 'SecurePass123' });

    // When
    const result = login(user.email, 'SecurePass123');

    // Then
    expect(result.success).toBe(true);
    expect(result.redirectTo).toBe('/dashboard');
  });
});
```

**Playwright/Cypress:**
```javascript
test('User can login successfully', async ({ page }) => {
  // Given
  await page.goto('/login');

  // When
  await page.fill('[name="email"]', 'user@example.com');
  await page.fill('[name="password"]', 'SecurePass123');
  await page.click('button[type="submit"]');

  // Then
  await expect(page).toHaveURL('/dashboard');
  await expect(page.locator('.welcome')).toBeVisible();
});
```

## Example Workflow Integration

```bash
# 1. Start workflow
/workflow:start-development-workflow "Add user authentication"

# 2. Create spec (SDD)
/workflow:create-workflow-spec
→ Creates OpenAPI spec for auth endpoints

# 3. Define behaviors (BDD)
/workflow:behavior-driven
→ Creates authentication.feature with scenarios

# 4. Get approval
→ Review spec + scenarios with stakeholders

# 5. Implement (TDD)
/workflow:implement
→ For each scenario:
  - Write failing test (RED)
  - Implement (GREEN)
  - Refactor (REFACTOR)

# 6. Verify
→ All scenarios pass
→ Acceptance criteria met
```

## Output Format

**BDD Scenarios File:**
```
Save to: features/<feature-name>.feature
Or: docs/bdd/<feature-name>.md

Include:
- Feature description
- User stories
- Scenarios (Given-When-Then)
- Examples/data tables
- Acceptance criteria checklist
```

## Error Handling

- **Ambiguous scenarios:** Ask for clarification
- **Too technical:** Refactor to business language
- **Missing edge cases:** Suggest additional scenarios
- **Conflicting requirements:** Flag for stakeholder review

## Integration Points

- **SDD (spec-driven):** Specs define what, BDD defines how users interact
- **TDD (test-driven):** BDD scenarios become test suites
- **Task Management:** Each scenario can become a task
- **Documentation:** Scenarios serve as living documentation
