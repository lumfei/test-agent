"""
MCP 工具集合 — Agent 的手和眼。
每个工具一个明确职责 + 明确边界条件。
"""

from src.tools.http_client import HTTPClient
from src.tools.schema_validator import SchemaValidator
from src.tools.test_data_gen import TestDataGenerator
from src.tools.web_doc_fetcher import WebDocFetcher
from src.tools.spec_parser import SpecParser
from src.tools.report_gen import ReportGenerator

# 单例实例
spec_parser = SpecParser()
http_client = HTTPClient()
schema_validator = SchemaValidator()
test_data_gen = TestDataGenerator()
web_fetcher = WebDocFetcher()
report_gen = ReportGenerator()

__all__ = [
    "spec_parser",
    "http_client",
    "schema_validator",
    "test_data_gen",
    "web_fetcher",
    "report_gen",
]
