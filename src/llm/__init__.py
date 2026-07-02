"""
DeepSeek LLM 客户端，兼容 OpenAI SDK 格式。
支持 Function Calling（工具调用）和结构化输出。
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from openai import OpenAI

from src.config import config


class DeepSeekClient:
    """DeepSeek V4 Flash LLM 客户端，OpenAI 兼容接口

    绕过系统代理：无论系统是否配置了 HTTP_PROXY/HTTPS_PROXY，
    都直连 DeepSeek API，避免代理导致的 SSL 错误。
    """

    def __init__(self):
        # trust_env=False 让 httpx 忽略系统代理环境变量，直连目标
        http_client = httpx.Client(trust_env=False)
        self.client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            http_client=http_client,
        )
        self.model = config.DEEPSEEK_MODEL

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        调用 DeepSeek Chat API。

        Args:
            messages: OpenAI 格式的消息列表
            tools: OpenAI 格式的工具定义（Function Calling）
            temperature: 采样温度（0-2），推理任务建议 0.1-0.3
            max_tokens: 最大输出 token 数

        Returns:
            API 响应的完整对象
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        return response.model_dump()

    def chat_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        带工具调用的对话。

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            tools: 工具定义列表
            temperature: 采样温度
            max_tokens: 最大 token 数

        Returns:
            包含 content 和 tool_calls 的响应
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return self.chat(messages, tools=tools, temperature=temperature, max_tokens=max_tokens)

    def extract_tool_calls(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """从 API 响应中提取工具调用"""
        choices = response.get("choices", [])
        if not choices:
            return []
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        return tool_calls

    def extract_content(self, response: dict[str, Any]) -> str:
        """从 API 响应中提取文本内容"""
        choices = response.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "") or ""


# 全局单例
llm = DeepSeekClient()
