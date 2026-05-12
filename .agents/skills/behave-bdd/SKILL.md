---
name: behave-bdd
description: Write and execute Behavior-Driven Development (BDD) tests using the Python `behave` framework. Use this skill when you need to create, update, or run BDD scenarios, write Gherkin feature files, or implement testing step definitions in Python.
---

# Behave BDD Skill

## Overview

The `behave-bdd` skill enables you to efficiently manage Behavior-Driven Development testing in python using the `behave` module. It outlines the directory structure required by `behave` and provides guidelines for writing both the requirement-level `.feature` files and the code-level step implementations.

## Directory Structure

When working with `behave`, you **must** adhere to the following directory layout:

```text
features/
├── example.feature          # Gherkin scenarios
├── steps/
│   └── example_steps.py     # Python implementations for the steps
└── environment.py           # Optional: For setup/teardown hooks and environmental controls
```

- All `.feature` files must reside in a directory named `features/`.
- All Python step definition `.py` files must reside in a subdirectory called `features/steps/`.
- `behave` works by discovering the `features/` directory in the current working directory, parsing the `.feature` files, and executing the mapped Python functions.

## Workflow

When asked to create or update a test using `behave`:

1.  **Analyze the Requirement:** Determine what behavior the user wants to test.
2.  **Write/Update the Feature File:**
    -   Create or modify a `.feature` file in the `features/` directory.
    -   Use proper Gherkin syntax (`Feature`, `Scenario`, `Given`, `When`, `Then`).
    -   *Reference: Review `references/gherkin_syntax.md` for proper formatting.*
3.  **Implement Step Definitions:**
    -   Create or modify Python scripts in `features/steps/`.
    -   Write python functions mapped to the feature steps using decorators (`@given`, `@when`, `@then`).
    -   Store any shared state in the `context` object.
    -   *Reference: Review `references/python_steps.md` for implementation details.*
4.  **Execute the Tests:**
    -   Run `behave` from the terminal at the root directory (the parent of `features/`).
    -   Command: `behave` or `python -m behave`

## Resources Included

**References:**
-   **`references/gherkin_syntax.md`**: Syntax rules and structure for writing `.feature` files.
-   **`references/python_steps.md`**: Guidelines for implementing testing logic in Python and utilizing the `context` object.

**Assets:**
-   **`assets/features/`**: Boilerplate template structure for starting a new BDD project.

## Execution Requirements
Be sure to actually `behave` tests natively in the terminal to verify functionality. If tests fail, iterate on the code in `features/steps/*.py` or fix the regular expressions/parsers to ensure the steps perfectly match the text in the `.feature` files.
