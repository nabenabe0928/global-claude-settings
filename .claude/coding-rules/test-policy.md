# Code quality
Test code is maintained to the same quality standard as production code:

## Rules
- Mirror the main source tree.
    - Example: the tests for `src/logging.py` live in `tests/test_logging.py`.
- Follow SOLID (Single responsibility, Open–closed, Liskov substitution, Interface segregation, Dependency inversion) and DRY (Don't Repeat Yourself).
    - DRY: Avoid redundancy in the test code.
        - Merge into a common module and parametrize with `pytest.mark.parametrize` if multiple classes/functions have duplicated test patterns.
        - Abstract duplicated logic into shared testing utility modules.
        - Avoid creating multiple test cases for a single equivalence class.
        - Avoid Copy and paste'ing test code.
- Cover sufficient boundary value analysis and equivalence partitioning.
    - Make tests reproducible.
        - Focus on single-worker scenarios unless the project explicitly guarantees reproducibility under parallelism.
    - Cover edge cases and error conditions. Typical edge cases include:
        - `None`, empty list, empty string, etc. 
        - `NaN`, `inf`, `-inf`, negative values, etc.
        - empty or uninitialized state (e.g., no data has been added yet).
        - a method is called before its prerequisites are satisfied.
- Reduce the fragility and prioritize the maintainability.
    - Avoid side effects to other test cases.
    - Avoid testing private methods/variables encapsulated in another class.
    - Avoid dependencies on unstable APIs or libraries.
    - Avoid conditional test logic for parameterized test case that deals with specific classes/functions.
    - Avoid unreasonable and fragile test cases.
        - Refactor to use more testable design and architecture if an API is unstable or hard to test.
        - Unreasonable testing on private APIs may cause the Fragile Tests problem.
- Test private methods and functions if they contain non-trivial logic.
- Follow XUnit Test Patterns to improve the test code quality.
- Make the test code readable. Describe the purpose sufficiently by the testing method name.
- Use both unit and visual regression testings for visualization modules.
    - Unit testing focuses on the verification of a small unit of source code, like a method or a function.
    - Visual regression testing is better suited for verifying the entire rendering pipeline, including visualization libraries.
