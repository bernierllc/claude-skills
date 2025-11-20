"""
Pytest configuration and shared fixtures for Google Slides tests.

This file provides common fixtures and configuration used across
all test modules to ensure consistency and reduce duplication.
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_anthropic_client():
    """
    Create a mock Anthropic client for testing.

    Returns a mock client with messages.create() method that returns
    configurable responses.
    """
    client = Mock()
    response = Mock()
    response.content = [Mock(text="Default mock response")]
    client.messages.create.return_value = response
    return client


@pytest.fixture
def mock_slides_service():
    """
    Create a mock Google Slides API service.

    Returns a mock service with presentations() method chain
    for get() and batchUpdate() operations.
    """
    service = Mock()
    presentations = Mock()
    service.presentations.return_value = presentations
    return service


@pytest.fixture
def mock_drive_service():
    """
    Create a mock Google Drive API service.

    Returns a mock service for Drive operations like comments.
    """
    return Mock()


@pytest.fixture
def sample_presentation_data():
    """
    Create sample presentation data structure.

    Returns a dictionary mimicking Google Slides API presentation response
    with slides, elements, and properties.
    """
    return {
        'presentationId': 'test_presentation_id',
        'title': 'Test Presentation',
        'pageSize': {
            'width': {'magnitude': 720, 'unit': 'PT'},
            'height': {'magnitude': 540, 'unit': 'PT'}
        },
        'slides': [
            {
                'objectId': 'slide1',
                'pageElements': [
                    {
                        'objectId': 'title_element',
                        'shape': {
                            'shapeType': 'TEXT_BOX',
                            'text': {
                                'textElements': [
                                    {
                                        'textRun': {
                                            'content': 'Slide Title',
                                            'style': {
                                                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                                                'fontFamily': 'Arial'
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    {
                        'objectId': 'content_element',
                        'shape': {
                            'shapeType': 'TEXT_BOX',
                            'text': {
                                'textElements': [
                                    {
                                        'textRun': {
                                            'content': 'Slide content goes here.',
                                            'style': {
                                                'fontSize': {'magnitude': 14, 'unit': 'PT'}
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ],
                'slideProperties': {
                    'notesPage': {
                        'objectId': 'notes1',
                        'pageElements': []
                    }
                }
            }
        ]
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_api: marks tests that require actual API access"
    )
