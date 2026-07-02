"""
Pytest fixtures and shared test configuration.
"""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_openapi_spec():
    """Minimal valid OpenAPI 3.0 spec for testing."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "servers": [{"url": "http://localhost:8000"}],
        "paths": {
            "/api/users": {
                "get": {
                    "summary": "List users",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "users": {"type": "array"},
                                            "total": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "summary": "Create user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string", "format": "email"},
                                    },
                                    "required": ["name", "email"],
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            }
        },
    }


@pytest.fixture
def sample_swagger_spec():
    """Minimal valid Swagger 2.0 spec for testing."""
    return {
        "swagger": "2.0",
        "info": {"title": "Test Swagger API", "version": "1.0.0"},
        "host": "api.example.com",
        "basePath": "/v1",
        "schemes": ["https"],
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get users",
                    "parameters": [],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


@pytest.fixture
def golden_dataset():
    with open(os.path.join(os.path.dirname(__file__), "golden_dataset.json"), "r", encoding="utf-8") as f:
        return json.load(f)
