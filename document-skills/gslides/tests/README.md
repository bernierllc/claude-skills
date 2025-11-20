# Google Slides Skill Test Suite

Comprehensive test suite for the Google Slides skill covering all core modules with mocked API calls.

## Test Coverage

### Core Modules Tested

1. **test_content_synthesizer.py** (62 tests)
   - Initialization with/without API key
   - Content synthesis from raw notes
   - Parsing multi-level bullet points
   - Error handling and edge cases
   - Special character and Unicode support

2. **test_story_arc_generator.py** (58 tests)
   - Story arc generation for different types (Hero's Journey, Problem-Solution, Before-After)
   - Arc scoring and validation
   - Narrative flow improvements
   - Segment parsing and handling

3. **test_whimsy_injector.py** (67 tests)
   - Personality injection at minimal/moderate/maximal levels
   - Appropriateness validation
   - Metaphor and analogy generation
   - Storytelling element enhancement
   - Result metadata tracking

4. **test_quality_checker.py** (89 tests)
   - Design quality (WCAG contrast, hierarchy, whitespace, alignment)
   - Content quality (grammar, clarity, audience, story arc)
   - Technical quality (images, fonts, links, objects)
   - Functional quality (slide count, reading level, accessibility)
   - Comprehensive quality aggregation

5. **test_comment_manager.py** (78 tests)
   - Comment CRUD operations
   - Element-specific suggestions
   - Attribution management (slide/notes/both)
   - Change tracking with timestamps
   - Edge case handling

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_quality_checker.py
```

### Run Specific Test Class
```bash
pytest tests/test_content_synthesizer.py::TestSynthesizeFromNotes
```

### Run Specific Test
```bash
pytest tests/test_whimsy_injector.py::TestPersonalityInjection::test_inject_minimal_personality
```

### Run with Verbose Output
```bash
pytest -v
```

### Run with Coverage Report
```bash
pytest --cov=scripts --cov-report=html
```

### Run Excluding Slow Tests
```bash
pytest -m "not slow"
```

## Test Structure

All tests use mocked API calls to avoid:
- Real Google Slides API requests
- Real Anthropic Claude API requests
- Real file system modifications

### Mocking Strategy

- **Google Slides API**: Mocked using `unittest.mock.Mock`
- **~~Anthropic API~~**: Phase 5 works through Claude - no external API mocking needed
- **File Operations**: Not used in tests (all in-memory)

**Note**: Phase 5 AI features work through Claude skill invocation, so no Anthropic API mocking is required.

### Fixtures

Common fixtures in `conftest.py`:
- ~~`mock_anthropic_client`~~: No longer needed - Phase 5 works through Claude
- `mock_slides_service`: Mock Google Slides service
- `mock_drive_service`: Mock Google Drive service
- `sample_presentation_data`: Sample presentation structure

## Test Quality Metrics

### Current Coverage
- **Target**: 80%+ code coverage on core logic
- **Actual**: Comprehensive coverage of public APIs
- **Edge Cases**: Extensive edge case testing
- **Error Handling**: All error paths tested

### Test Categories

1. **Initialization Tests**: Verify proper setup
2. **Success Path Tests**: Normal operation scenarios
3. **Error Handling Tests**: API failures and invalid inputs
4. **Edge Case Tests**: Empty data, very long data, special characters
5. **Integration Tests**: Multi-component workflows (marked with `@pytest.mark.integration`)

## Writing New Tests

### Template for New Test Module

```python
"""
Tests for new_module.py

Brief description of what this module does.
"""

import pytest
from unittest.mock import Mock, patch
from scripts.new_module import NewClass


class TestNewClassInitialization:
    """Test NewClass initialization."""

    def test_init_with_config(self):
        """Test initialization with configuration."""
        obj = NewClass(config="value")
        assert obj.config == "value"


class TestMainFunctionality:
    """Test main functionality."""

    @patch('scripts.new_module.ExternalDependency')
    def test_main_function(self, mock_dependency):
        """Test main function with mocked dependencies."""
        # Setup mock
        mock_dependency.return_value = "expected"

        # Run test
        result = NewClass().main_function()

        # Verify
        assert result == "expected"
```

### Best Practices

1. **One concept per test**: Each test should validate one specific behavior
2. **Clear test names**: Use descriptive names like `test_function_with_valid_input_returns_expected_output`
3. **AAA Pattern**: Arrange (setup), Act (execute), Assert (verify)
4. **Mock external dependencies**: Never make real API calls
5. **Test edge cases**: Empty inputs, very long inputs, special characters, errors
6. **Document expected behavior**: Use docstrings to explain what each test validates

## Continuous Integration

Tests run automatically on:
- Pre-commit hooks (if configured)
- Pull request creation
- Merge to main branch

All tests must pass before merging.

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure you're in the correct directory
cd /path/to/gslides
# Install dependencies
pip install -r requirements.txt
```

**Mock Not Working**
```python
# Ensure correct patch path
@patch('scripts.module_name.ClassName')  # Full path from scripts/
```

**Test Discovery Issues**
```bash
# Verify pytest can find tests
pytest --collect-only
```

## Future Enhancements

- [ ] Add performance benchmarking tests
- [ ] Add integration tests with real API (marked as optional)
- [ ] Add property-based testing with Hypothesis
- [ ] Add mutation testing to verify test quality
- [ ] Add visual regression testing for generated slides
