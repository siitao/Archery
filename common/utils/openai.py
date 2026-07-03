from openai import OpenAI
import logging
from common.config import SysConfig
from django.template import Context, Template

logger = logging.getLogger("default")


class OpenaiClient:
    def __init__(self):
        all_config = SysConfig()
        self.base_url = all_config.get("openai_base_url", "")
        self.api_key = all_config.get("openai_api_key", "")
        self.default_chat_model = all_config.get("default_chat_model", "gpt-3.5-turbo")
        self.default_query_template = all_config.get(
            "default_query_template",
            "你是一个熟悉 {{db_type}} 的工程师, 我会给你一些基本信息和要求, 你会生成一个查询语句给我使用, 不要返回任何注释和序号, 仅返回查询语句：{{table_schema}} \n {{user_input}}",
        )
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def request_chat_completion(self, messages, **kwargs):
        """chat_completion"""
        completion = self.client.chat.completions.create(
            model=self.default_chat_model, messages=messages, **kwargs
        )
        return completion

    def generate_sql_by_openai(self, db_type: str, table_schema: str, user_input: str):
        """根据传入的基本信息生成查询语句"""
        template = Template(self.default_query_template)
        current_context = Context(
            dict(db_type=db_type, table_schema=table_schema, user_input=user_input)
        )
        messages = [dict(role="user", content=template.render(current_context))]
        logger.info(messages)
        try:
            res = self.request_chat_completion(messages)
            return res.choices[0].message.content
        except Exception as e:
            raise ValueError(f"请求openai生成查询语句失败: {e}")

    def analyze_sql_by_openai(self, sql_text: str):
        """对一段 SQL 进行语法/规范/潜在问题的评审，返回 markdown 报告"""
        prompt = (
            "你是一位资深的 DBA 和 SQL 审核专家。请对下面的 SQL 语句进行审核分析，"
            "从语法正确性、书写规范（关键字大小写/表别名/字段显式列出等）、"
            "潜在性能问题（如 SELECT *、缺少 WHERE、隐式类型转换、OR 条件、LIKE 前缀通配等）、"
            "安全风险（SQL 注入、危险操作）等方面给出评审意见。\n"
            "请用 Markdown 格式输出，结构清晰，包含「问题清单」和「改进建议」两部分，"
            "每条建议尽量给出修改前后的对比示例。不要输出与 SQL 无关的内容。\n\n"
            f"待审核的 SQL：\n{sql_text}"
        )
        messages = [dict(role="user", content=prompt)]
        logger.info(messages)
        try:
            res = self.request_chat_completion(messages)
            return res.choices[0].message.content
        except Exception as e:
            raise ValueError(f"请求openai分析SQL失败: {e}")

    def optimize_sql_by_openai(
        self,
        db_type: str,
        db_name: str,
        sql_text: str,
        table_schemas: str,
    ):
        """结合表结构上下文，对 SQL 给出优化建议，返回 markdown 报告"""
        prompt = (
            f"你是一位资深的 {db_type} DBA 和性能优化专家。"
            "请结合下面提供的表结构信息，对目标 SQL 给出优化建议，"
            "包括但不限于：索引建议（是否缺少索引、是否有更优索引）、"
            "SQL 改写建议、潜在的全表扫描/临时表/文件排序风险、"
            "以及执行计划的解读要点。\n"
            "请用 Markdown 格式输出结构清晰的优化报告，"
            "索引建议请给出对应的 DDL 语句，改写建议请给出修改前后的 SQL 对比。"
            "不要输出与优化无关的内容。\n\n"
            f"数据库：{db_name}\n"
            f"相关表结构：\n{table_schemas}\n\n"
            f"目标 SQL：\n{sql_text}"
        )
        messages = [dict(role="user", content=prompt)]
        logger.info(messages)
        try:
            res = self.request_chat_completion(messages)
            return res.choices[0].message.content
        except Exception as e:
            raise ValueError(f"请求openai优化SQL失败: {e}")


def check_openai_config():
    """校验openai必需配置openai_api_key是否存在"""
    all_config = SysConfig()
    api_key = all_config.get("openai_api_key")
    if api_key:
        return True
    return False


def test_openai_connection(base_url=None, api_key=None, model=None):
    """测试 AI 服务连通性。

    可显式传入临时参数（用于配置页"测试连接"，此时尚未保存）；
    不传则读取 SysConfig 已保存的配置。发送一个最简 chat 请求验证。
    成功返回 (True, 模型名)，失败返回 (False, 错误信息)。
    """
    all_config = SysConfig()
    base_url = base_url if base_url is not None else all_config.get("openai_base_url", "")
    api_key = api_key if api_key is not None else all_config.get("openai_api_key", "")
    model = model if model is not None else all_config.get(
        "default_chat_model", "gpt-3.5-turbo"
    )
    if not api_key:
        return False, "AI API Key 未配置"
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        client.close()
        return True, model
    except Exception as e:
        return False, str(e)
