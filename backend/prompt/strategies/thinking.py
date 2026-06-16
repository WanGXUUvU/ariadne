"""不同模型的 thinking 参数风格配置。

每种 style 描述：
- enable_payload：开启思考时合并进请求 body 的参数（"{effort}" 为占位符）
- disable_payload：关闭思考时合并进请求 body 的参数
- effort_levels：支持的档位列表，空列表表示无档位可选（开关型）
- effort_map：可选，将档位字符串映射为实际参数值（整数等非字符串类型）
- default_effort：默认档位，无档位时为空字符串

当前各厂商格式：
  deepseek_style  — DeepSeek 全系列（V4/R1/R2 等）：thinking.type + reasoning_effort 双字段格式，支持 low/medium/high
  sensenova_style — SenseNova：reasoning_effort 顶层参数，"none" 表示关闭，支持 low/medium/high
  claude_style    — Anthropic Claude：thinking.type + budget_tokens，low=4K/medium=10K/high=32K tokens
  kimi_style      — Kimi k 系列：thinking.type 控制开关，无档位
  glm_style       — GLM-5.1/5/4.7：thinking.type 控制开关（格式与 kimi 相同），无档位
  qwen_style      — Qwen3 / QwQ：enable_thinking 顶层参数，无档位
  openai_style    — OpenAI gpt-5.1+ 系列：reasoning_effort 顶层参数，支持 low/medium/high/xhigh
  always_on_style — 始终思考型（MiniMax-M2 等）：thinking 训练进去无法关闭，payload 为空，
                    响应中以 <think>...</think> 标签包裹思考内容，无档位
  none            — 不支持 thinking（MiniMax-Text-01 等），所有 payload 为空
"""

import copy

THINKING_STYLES = {
    "deepseek_style": {
        # DeepSeek 全系列（V4/R1/R2 等）：thinking.type + reasoning_effort 双字段格式
        # thinking.type 控制开关，reasoning_effort 控制深度
        "enable_payload": {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "{effort}",
        },
        "disable_payload": {"thinking": {"type": "disabled"}},
        "effort_levels": ["low", "medium", "high"],
        "default_effort": "medium",
    },
    "sensenova_style": {
        # SenseNova：reasoning_effort 直接放 body 顶层，"none" 表示关闭
        "enable_payload": {"reasoning_effort": "{effort}"},
        "disable_payload": {"reasoning_effort": "none"},
        "effort_levels": ["low", "medium", "high"],
        "default_effort": "medium",
    },
    "kimi_style": {
        # Kimi k2.6：thinking 字段控制开关，默认就是 enabled，无档位
        "enable_payload": {"thinking": {"type": "enabled"}},
        "disable_payload": {"thinking": {"type": "disabled"}},
        "effort_levels": [],
        "default_effort": "",
    },
    "glm_style": {
        # GLM-5.1/5/4.7：thinking 字段控制开关，默认就是 enabled，无档位
        # 官方文档：{"thinking": {"type": "disabled"}} 关闭，{"thinking": {"type": "enabled"}} 开启
        "enable_payload": {"thinking": {"type": "enabled"}},
        "disable_payload": {"thinking": {"type": "disabled"}},
        "effort_levels": [],
        "default_effort": "",
    },
    "claude_style": {
        # Anthropic Claude Extended Thinking：budget_tokens 控制思考深度
        # low≈4K / medium≈10K / high≈32K tokens
        "enable_payload": {
            "thinking": {"type": "enabled", "budget_tokens": "{effort}"}
        },
        "disable_payload": {"thinking": {"type": "disabled"}},
        "effort_levels": ["low", "medium", "high"],
        "effort_map": {"low": 4000, "medium": 10000, "high": 32000},
        "default_effort": "medium",
    },
    "qwen_style": {
        # Qwen3 / QwQ 系列：enable_thinking 顶层参数（可选 thinking_budget 控制深度，此处不传）
        "enable_payload": {"enable_thinking": True},
        "disable_payload": {"enable_thinking": False},
        "effort_levels": [],
        "default_effort": "",
    },
    "openai_style": {
        # OpenAI gpt-5.1 及以上系列：支持额外的 xhigh 档位
        "enable_payload": {"reasoning_effort": "{effort}"},
        "disable_payload": {},
        "effort_levels": ["low", "medium", "high", "xhigh"],
        "default_effort": "medium",
    },
    "always_on_style": {
        # 始终思考型模型（MiniMax-M2 等）：thinking 训练进去无法通过 API 控制
        # 响应中以 <think>...</think> 包裹思考过程，无任何 payload 可发
        # supports_thinking=True 以便 UI 显示思考内容，但开关对 API 无实际影响
        "enable_payload": {},
        "disable_payload": {},
        "effort_levels": [],
        "default_effort": "",
    },
    "none": {
        # 不支持 thinking 的模型（MiniMax-Text-01 等），payload 均为空
        "enable_payload": {},
        "disable_payload": {},
        "effort_levels": [],
        "default_effort": "",
    },
}


def build_thinking_payload(style: str, enabled: bool, effort: str) -> dict:
    """返回需要合并进请求 body 的 thinking 参数。

    - style 不存在或为 "none"：返回 {}
    - enabled=False：返回 disable_payload
    - enabled=True：递归替换 enable_payload 中的 "{effort}" 占位符；
      若 style 配置了 effort_map，则先将档位字符串映射为对应值（整数等）
    """
    cfg = THINKING_STYLES.get(style)
    if not cfg or style == "none":
        return {}

    if not enabled:
        return cfg.get("disable_payload", {})

    payload = copy.deepcopy(cfg["enable_payload"])
    effort_map = cfg.get("effort_map")
    # effort_map 存在时取映射值（可能是 int），否则直接用字符串
    effort_value = effort_map[effort] if effort_map and effort in effort_map else effort

    def _replace(obj):
        """递归替换 dict/str 中的 "{effort}" 占位符。"""
        if isinstance(obj, str) and obj == "{effort}":
            return effort_value
        if isinstance(obj, dict):
            return {k: _replace(v) for k, v in obj.items()}
        return obj

    return _replace(payload)


def get_effort_levels(style: str) -> list[str]:
    """返回指定 style 支持的档位列表，供前端渲染用。"""
    cfg = THINKING_STYLES.get(style, {})
    return cfg.get("effort_levels", [])
