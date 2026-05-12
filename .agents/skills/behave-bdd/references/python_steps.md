# Python Step Definitions Reference

Step definitions map the steps in `.feature` files to Python code, allowing the tests to execute. They are typically placed in `features/steps/*.py`.

## Basic Structure

```python
from behave import given, when, then

@given('we have behave installed')
def step_impl(context):
    pass # Implementation goes here

@when('we implement a test')
def step_impl(context):
    assert True is not False

@then('behave will test it for us!')
def step_impl(context):
    assert context.failed is False
```

## Context Object

The `context` object is passed to every step and is used to store state during the execution of a feature/scenario.

```python
@given('a user "{username}" exists')
def step_impl(context, username):
    context.username = username # Save state

@then('the user should be logged in')
def step_impl(context):
    assert hasattr(context, 'username')
    # Validate login state
```

## Matching Parameters

### 1. Parse Matcher (Default)
Extract arguments from the step text.
```python
@given('I have {count:d} apples')
def step_impl(context, count):
    assert isinstance(count, int)
```

### 2. Regex Matcher
For more complex parsing, you can use regular expressions. To enable this, configure the matcher in the `environment.py` or set it in the step file.
```python
from behave import use_step_matcher, given
use_step_matcher("re")

@given(r'I have (?P<count>\d+) apples')
def step_impl(context, count):
    assert isinstance(count, str) # Regex always captures as strings unless type hinted
```

## Assertions
Standard python `assert` is used to fail a step.
```python
@then('the result should be {expected}')
def step_impl(context, expected):
    assert context.result == expected, f"Expected {expected}, but got {context.result}"
```

## Tables and Text
You can access multi-line text or tables provided in the feature file.
```python
@given('a set of specific users')
def step_impl(context):
    for row in context.table:
        print(row['name'], row['department'])

@given('a complex document')
def step_impl(context):
    print(context.text)
```
