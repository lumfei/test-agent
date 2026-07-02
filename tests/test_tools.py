"""
Unit tests for agent tools — spec_parser, test_data_gen, http_client, schema_validator.
"""
import pytest
import json
from src.tools.spec_parser import SpecParser, ParsedSpec
from src.tools.test_data_gen import TestDataGenerator, TestCase, TestSuite
from src.tools.schema_validator import SchemaValidator


class TestSpecParser:
    """Tests for OpenAPI spec parsing."""

    def test_parse_openapi_v3(self, sample_openapi_spec):
        parser = SpecParser()
        result = parser.parse(sample_openapi_spec)
        assert isinstance(result, ParsedSpec)
        assert result.title == "Test API"
        assert result.version == "1.0.0"
        assert len(result.endpoints) == 2  # GET + POST /api/users
        assert result.base_url == "http://localhost:8000"

    def test_parse_swagger_v2(self, sample_swagger_spec):
        parser = SpecParser()
        result = parser.parse(sample_swagger_spec)
        assert result.title == "Test Swagger API"
        assert result.base_url == "https://api.example.com/v1"
        assert len(result.endpoints) == 1

    def test_parse_no_servers_fallback(self, sample_openapi_spec):
        spec = dict(sample_openapi_spec)
        del spec["servers"]
        parser = SpecParser()
        result = parser.parse(spec)
        assert result.base_url == ""  # No servers declared

    def test_endpoint_extraction(self, sample_openapi_spec):
        parser = SpecParser()
        result = parser.parse(sample_openapi_spec)
        endpoints = {(ep.method, ep.path) for ep in result.endpoints}
        assert ("GET", "/api/users") in endpoints
        assert ("POST", "/api/users") in endpoints

    def test_request_body_schema(self, sample_openapi_spec):
        parser = SpecParser()
        result = parser.parse(sample_openapi_spec)
        post_ep = [ep for ep in result.endpoints if ep.method == "POST"][0]
        assert post_ep.request_body_schema is not None
        assert "name" in post_ep.request_body_schema.get("properties", {})
        assert "email" in post_ep.request_body_schema.get("properties", {})

    def test_parameters_extraction(self, sample_openapi_spec):
        parser = SpecParser()
        result = parser.parse(sample_openapi_spec)
        get_ep = [ep for ep in result.endpoints if ep.method == "GET"][0]
        assert len(get_ep.parameters) == 1
        assert get_ep.parameters[0]["name"] == "limit"

    def test_to_summary_text(self, sample_openapi_spec):
        parser = SpecParser()
        parsed = parser.parse(sample_openapi_spec)
        text = parser.to_summary_text(parsed)
        assert "Test API" in text
        assert "GET" in text
        assert "POST" in text

    def test_parse_invalid_spec(self):
        parser = SpecParser()
        with pytest.raises(ValueError, match="不支持的规范格式"):
            parser.parse({"info": {"title": "Not a spec"}})

    def test_auth_detection(self, sample_openapi_spec):
        spec = dict(sample_openapi_spec)
        spec["paths"]["/api/users"]["post"]["security"] = [{"bearerAuth": []}]
        parser = SpecParser()
        result = parser.parse(spec)
        assert result.auth_required is True


class TestTestDataGenerator:
    """Tests for test case generation."""

    def test_generate_normal_case(self):
        gen = TestDataGenerator()
        cases = gen.generate_normal_cases("GET", "/users")
        assert len(cases) == 1
        assert cases[0].category == "normal"
        assert cases[0].expected_status == 200

    def test_generate_boundary_cases(self):
        gen = TestDataGenerator()
        cases = gen.generate_boundary_cases("POST", "/users")
        # POST: empty body + oversized + unicode
        assert len(cases) >= 2
        categories = {c.category for c in cases}
        assert "boundary" in categories

    def test_generate_error_cases(self):
        gen = TestDataGenerator()
        # GET with no params: only wrong-method (body tests are meaningless)
        cases_get = gen.generate_error_cases("GET", "/users")
        assert len(cases_get) >= 1
        wrong_method = [c for c in cases_get if "wrong method" in c.name]
        assert len(wrong_method) == 1

        # POST with body: wrong method + wrong content-type + malformed JSON
        cases_post = gen.generate_error_cases("POST", "/users")
        assert len(cases_post) >= 3

        # GET with string params: should also get oversized query test
        cases_params = gen.generate_error_cases("GET", "/users", [
            {"name": "q", "in": "query", "schema": {"type": "string"}}
        ])
        assert len(cases_params) >= 2  # wrong method + oversized query

    def test_generate_security_cases_no_auth(self):
        gen = TestDataGenerator()
        cases = gen.generate_security_cases("GET", "/users", auth_required=False)
        # No auth required → no auth-related security cases
        assert all("no auth" not in c.name.lower() for c in cases)

    def test_generate_security_cases_with_auth(self):
        gen = TestDataGenerator()
        cases = gen.generate_security_cases("POST", "/users", auth_required=True)
        has_no_auth = any("no auth" in c.name.lower() for c in cases)
        has_invalid_token = any("invalid token" in c.name.lower() for c in cases)
        assert has_no_auth
        assert has_invalid_token

    def test_generate_security_sql_injection(self):
        gen = TestDataGenerator()
        cases = gen.generate_security_cases(
            "POST", "/users",
            parameters=[{"name": "q", "in": "query", "schema": {"type": "string"}}],
        )
        sql_cases = [c for c in cases if "sql injection" in c.name.lower()]
        assert len(sql_cases) > 0

    def test_generate_security_xss(self):
        gen = TestDataGenerator()
        cases = gen.generate_security_cases(
            "GET", "/search",
            parameters=[{"name": "q", "in": "query", "schema": {"type": "string"}}],
        )
        xss_cases = [c for c in cases if "xss" in c.name.lower()]
        assert len(xss_cases) > 0

    def test_generate_full_suite(self):
        gen = TestDataGenerator()
        suite = gen.generate_full_suite(
            api_name="Test", base_url="http://localhost", method="POST", path="/users",
            parameters=[{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
            request_body_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            auth_required=True,
        )
        assert isinstance(suite, TestSuite)
        assert suite.case_count > 5
        categories = {c.category for c in suite.cases}
        assert "normal" in categories
        assert "boundary" in categories
        assert "error" in categories
        assert "security" in categories

    def test_path_parameter_substitution(self):
        gen = TestDataGenerator()
        params = [
            {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}},
        ]
        suite = gen.generate_full_suite(
            api_name="Test", base_url="http://localhost", method="GET",
            path="/api/users/{id}", parameters=params,
        )
        for case in suite.cases:
            assert "{id}" not in case.path

    def test_valid_body_generation(self):
        gen = TestDataGenerator()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"},
            },
        }
        body = gen._gen_valid_body(schema)
        assert isinstance(body, dict)
        assert body["name"] == "test_value"
        assert body["age"] == 1
        assert body["active"] is True

    def test_anyof_type_resolution(self):
        gen = TestDataGenerator()
        schema = {
            "type": "object",
            "properties": {
                "temperature": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                "max_tokens": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
        }
        body = gen._gen_valid_body(schema)
        assert isinstance(body["temperature"], float)
        assert isinstance(body["max_tokens"], int)

    def test_resolve_path_params(self):
        gen = TestDataGenerator()
        params = [
            {"name": "userId", "in": "path", "schema": {"type": "integer"}},
            {"name": "orderId", "in": "path", "schema": {"type": "string"}},
        ]
        result = gen._resolve_path_params("/api/users/{userId}/orders/{orderId}", params)
        assert "{userId}" not in result
        assert "{orderId}" not in result
        assert "/api/users/1/orders/" in result


class TestSchemaValidator:
    """Tests for JSON Schema validation."""

    def test_validate_status_code_match(self):
        sv = SchemaValidator()
        result = sv.validate_status_code(200, 200)
        assert result.passed is True

    def test_validate_status_code_mismatch(self):
        sv = SchemaValidator()
        result = sv.validate_status_code(500, 200)
        assert result.passed is False

    def test_validate_status_code_list(self):
        sv = SchemaValidator()
        result = sv.validate_status_code(200, [200, 201])
        assert result.passed is True
        result = sv.validate_status_code(500, [200, 201])
        assert result.passed is False

    def test_validate_json_schema_valid(self):
        sv = SchemaValidator()
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = sv.validate_json_schema({"name": "test"}, schema)
        assert result.passed is True

    def test_validate_json_schema_invalid(self):
        sv = SchemaValidator()
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = sv.validate_json_schema({"name": 123}, schema)
        assert result.passed is False

    def test_validate_response_time_ok(self):
        sv = SchemaValidator()
        result = sv.validate_response_time(100)
        assert result.passed is True

    def test_validate_response_time_slow(self):
        sv = SchemaValidator()
        result = sv.validate_response_time(6000)
        assert result.passed is False


class TestGoldenDataset:
    """Verify golden dataset integrity."""

    def test_dataset_loads(self, golden_dataset):
        assert "cases" in golden_dataset
        assert len(golden_dataset["cases"]) >= 3

    def test_all_cases_have_ids(self, golden_dataset):
        for case in golden_dataset["cases"]:
            assert "id" in case
            assert "spec_url" in case
            assert "expected_bugs" in case

    def test_mock_case_exists(self, golden_dataset):
        mock_cases = [c for c in golden_dataset["cases"] if any("mock" in t for t in c.get("tags", []))]
        assert len(mock_cases) >= 1

    def test_healthy_case_exists(self, golden_dataset):
        healthy = [c for c in golden_dataset["cases"] if "healthy-api" in c.get("tags", [])]
        assert len(healthy) >= 1
