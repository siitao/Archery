import json
import logging
import re

from openai import OpenAI
from common.config import SysConfig
from django.template import Context, Template

logger = logging.getLogger("default")


# AI 审核：风险等级常量
AI_RISK_LOW = "low"
AI_RISK_MEDIUM = "medium"
AI_RISK_HIGH = "high"
AI_RISK_UNKNOWN = "unknown"

# AI 审核：DDL 锁表风险等级
AI_LOCK_NONE = "none"  # 非 DDL，无锁表风险
AI_LOCK_LOW = "low"  # DDL 但小表/在线变更，风险低
AI_LOCK_MEDIUM = "medium"  # 中等表，可能短暂锁
AI_LOCK_HIGH = "high"  # 大表 DDL，长时间锁表

# AI 审核默认占位（容错时返回，避免中断检测流程）
AI_REVIEW_FALLBACK = {
    "risk_level": AI_RISK_UNKNOWN,
    "risk_score": 0,
    "summary": "AI 审核跳过",
    "suggestion": "",
    "ddl_lock_risk": AI_LOCK_NONE,
    "affected_rows_estimate": "",
    "use_osc": False,
}


class OpenaiClient:
    def __init__(self):
        all_config = SysConfig()
        self.base_url = all_config.get("openai_base_url", "")
        self.api_key = all_config.get("openai_api_key", "")
        self.default_chat_model = all_config.get("default_chat_model", "gpt-3.5-turbo")
        self.default_query_template = all_config.get(
            "default_query_template",
            "你是一个熟悉 {{db_type}} 的资深工程师。\n"
            "请严格根据以下【表结构 DDL】中给出的表名和字段名，结合用户描述，生成一条可直接执行的查询 SQL。\n"
            "重要：只能使用 DDL 中出现的表名和字段名，禁止编造或推测不存在的表和字段。\n"
            "请参考【样本数据】中字段值的实际格式（如命名风格、编码方式），"
            "在 WHERE 条件中使用正确的值，而不是凭常识猜测。\n"
            "要求：仅返回 SQL 语句本身，不要返回注释、序号或 markdown 代码块。\n\n"
            "【表结构 DDL】\n{{table_schema}}\n\n"
            "【样本数据】\n{{sample_data}}\n\n"
            "【查询需求】\n{{user_input}}",
        )
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def request_chat_completion(self, messages, **kwargs):
        """chat_completion"""
        completion = self.client.chat.completions.create(
            model=self.default_chat_model, messages=messages, **kwargs
        )
        return completion

    def generate_sql_by_openai(self, db_type: str, table_schema: str, user_input: str, sample_data: str = ""):
        """根据传入的基本信息生成查询语句"""
        template = Template(self.default_query_template)
        current_context = Context(
            dict(db_type=db_type, table_schema=table_schema, user_input=user_input, sample_data=sample_data)
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

    def review_sql_by_openai(
        self,
        db_type: str,
        db_name: str,
        sql_text: str,
        table_schemas: str,
        table_rows: str,
    ):
        """对单条 SQL 做风险审核 + 变更影响预测，返回结构化结果。

        输出 dict：
            {
                "risk_level": "low" | "medium" | "high",
                "risk_score": int (0-100),
                "summary": str,                 # 一句话总结，供表格内展示
                "suggestion": str,              # 详细建议（markdown）
                "ddl_lock_risk": "none"|"low"|"medium"|"high",  # DDL 锁表风险
                "affected_rows_estimate": str,  # 影响行数预估（如 "约132万行"）
                "use_osc": bool                 # 是否建议走 gh-ost/pt-osc 在线变更
            }

        纯参考、不阻断：任何异常都返回 AI_REVIEW_FALLBACK（risk_level=unknown），
        绝不抛异常中断外层检测流程。
        """
        prompt = (
            f"你是一位资深的 {db_type} DBA 和 SQL 审核专家。请对下面这条待上线的 SQL 进行风险审核和变更影响预测。\n"
            "审核维度：\n"
            "1. 语法与规范：关键字大小写、表别名、SELECT *、缺显式字段等；\n"
            "2. 性能风险：是否有全表扫描、缺索引、LIKE 前缀通配、隐式类型转换、OR 条件、临时表/文件排序等；\n"
            "3. 数据量与锁：结合提供的表行数，判断 DDL 是否会长时间锁表（大表加索引/改字段）、"
            "DML 是否会扫描过多行；\n"
            "4. 安全风险：是否为危险操作（无 WHERE 的 UPDATE/DELETE、TRUNCATE、DROP）。\n\n"
            "变更影响预测（务必结合提供的表行数）：\n"
            "- ddl_lock_risk：DDL 语句的锁表风险等级。非 DDL 填 none；小表(<1万行)填 low；"
            "中等表(1万-100万)填 medium；大表(>100万)的加索引/改字段/改类型填 high。\n"
            "- affected_rows_estimate：预估影响的行数，用中文描述（如「约132万行」「全表约5000行」），非数据变更填空串。\n"
            "- use_osc：当 ddl_lock_risk 为 high 时填 true（建议走 gh-ost/pt-online-schema-change 在线变更），否则 false。\n\n"
            "评分标准（0-100，越高风险越大）：\n"
            "- 0-39：low（低风险，可放心执行）\n"
            "- 40-70：medium（中风险，需关注，建议在低峰执行或加限流）\n"
            "- 71-100：high（高风险，强烈建议改写、分批或走在线变更）\n\n"
            "请严格按如下 JSON 格式输出（仅输出 JSON，不要任何额外文字、不要 markdown 代码块）：\n"
            "输出要求：使用专业、严谨的技术措辞，不要使用任何 emoji 表情符号，不要使用口语化表达。\n"
            '{"risk_level": "low|medium|high", '
            '"risk_score": 整数, '
            '"summary": "一句话总结（≤40字，中文）", '
            '"suggestion": "详细建议（markdown，包含问题清单和修改前后的 SQL 对比）", '
            '"ddl_lock_risk": "none|low|medium|high", '
            '"affected_rows_estimate": "影响行数预估", '
            '"use_osc": true或false}\n\n'
            f"数据库：{db_name}\n"
            f"相关表行数：\n{table_rows}\n\n"
            f"相关表结构：\n{table_schemas}\n\n"
            f"待审核 SQL：\n{sql_text}"
        )
        messages = [dict(role="user", content=prompt)]
        try:
            res = self.request_chat_completion(messages)
            content = res.choices[0].message.content
            return self._parse_review_json(content)
        except Exception as e:
            logger.warning(f"AI 审核 SQL 失败，降级返回 unknown: {e}")
            return dict(AI_REVIEW_FALLBACK)

    @staticmethod
    def _parse_review_json(content: str):
        """解析 AI 返回的审核结果。

        兼容 LLM 常见的不规范输出：
        1. markdown 代码块包裹（```json ... ```）；
        2. JSON 前后有解释性文字（抽取首个 {...}）；
        3. 字符串值内含裸露换行符（违反 JSON 规范，需转义为 \\n）——这是 LLM
           在 JSON 里写多行 markdown 时的典型行为，最易导致解析失败。
        """
        if not content:
            return dict(AI_REVIEW_FALLBACK)
        text = content.strip()

        data = OpenaiClient._try_load_json(text)
        if data is None:
            # 去掉代码块包裹后重试
            stripped = text
            if stripped.startswith("```"):
                stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
                stripped = re.sub(r"\s*```$", "", stripped)
            data = OpenaiClient._try_load_json(stripped)
        if data is None:
            # 抽取首个 {...} 片段（DOTALL 跨行），再做换行容错
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = OpenaiClient._try_load_json(match.group(0))
        if data is None:
            logger.warning(f"AI 审核结果解析失败，原始内容: {content[:200]}")
            return dict(AI_REVIEW_FALLBACK)

        # 字段校验与归一
        level = str(data.get("risk_level", "")).lower()
        if level not in (AI_RISK_LOW, AI_RISK_MEDIUM, AI_RISK_HIGH):
            level = AI_RISK_UNKNOWN
        try:
            score = int(data.get("risk_score", 0))
            score = max(0, min(100, score))
        except (TypeError, ValueError):
            score = 0
        # DDL 锁表风险归一
        lock = str(data.get("ddl_lock_risk", AI_LOCK_NONE)).lower()
        if lock not in (AI_LOCK_NONE, AI_LOCK_LOW, AI_LOCK_MEDIUM, AI_LOCK_HIGH):
            lock = AI_LOCK_NONE
        # 影响行数预估（字符串，直接取）
        affected = str(data.get("affected_rows_estimate", "") or "")
        # use_osc 归一为 bool
        osc_raw = data.get("use_osc", False)
        if isinstance(osc_raw, str):
            use_osc = osc_raw.strip().lower() in ("true", "1", "yes")
        else:
            use_osc = bool(osc_raw)
        return {
            "risk_level": level,
            "risk_score": score,
            "summary": OpenaiClient._strip_emoji(
                str(data.get("summary", ""))[:200]
            )
            or "AI 审核完成",
            "suggestion": OpenaiClient._strip_emoji(
                str(data.get("suggestion", ""))
            ),
            "ddl_lock_risk": lock,
            "affected_rows_estimate": OpenaiClient._strip_emoji(affected),
            "use_osc": use_osc,
        }

    @staticmethod
    def _strip_emoji(text: str) -> str:
        """移除 emoji 表情及杂项符号，保持输出专业。

        覆盖常见 emoji 区块：杂项符号与象形文字、表情符号、补充符号、
        交通符号、旗帜等。同时压缩 emoji 移除后可能残留的多余空白。
        """
        if not text:
            return text
        cleaned = re.sub(
            "["
            "\U0001F300-\U0001FAFF"  # 符号与象形文字 / 表情符号 / 补充
            "\U00002600-\U000027BF"  # 杂项符号 / 装饰符号
            "\U0001F1E6-\U0001F1FF"  # 旗帜区域指示符
            "\U0001F900-\U0001F9FF"  # 补充符号与象形文字
            "]+",
            "",
            text,
        )
        # 压缩因 emoji 删除产生的连续空白（但保留换行）
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _try_load_json(text: str):
        """尝试解析 JSON，对 LLM 常见不规范输出做多层容错修复。

        依次尝试：
        1. 直接 json.loads；
        2. 字符串值内裸露换行符/制表符转义；
        3. 去除尾部逗号（],} 前的 ,）；
        4. 单引号 → 双引号（仅键名/标量，逐字符扫描避免误伤字符串内容）；
        5. 中文标点（“”‘’，：）替换为 ASCII 标点。

        返回解析后的 dict，或 None（解析失败）。
        """
        # 第1层：直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 第2层：字符串值内裸露控制字符转义（逐字符扫描，跟踪是否在字符串内）
        escaped = []
        in_str = False
        escape = False
        for ch in text:
            if escape:
                escaped.append(ch)
                escape = False
                continue
            if ch == "\\":
                escaped.append(ch)
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                escaped.append(ch)
                continue
            if in_str and ch == "\n":
                escaped.append("\\n")
            elif in_str and ch == "\r":
                escaped.append("\\r")
            elif in_str and ch == "\t":
                escaped.append("\\t")
            else:
                escaped.append(ch)
        text2 = "".join(escaped)
        try:
            return json.loads(text2)
        except json.JSONDecodeError:
            pass

        # 第3层：去除尾部逗号（}, ] 前的逗号，可能带空白）
        text3 = re.sub(r",\s*([}\]])", r"\1", text2)
        if text3 != text2:
            try:
                return json.loads(text3)
            except json.JSONDecodeError:
                pass

        # 第4层：中文全角标点 → ASCII（LLM 中文输出常带全角逗号/冒号/引号）
        text4 = text3.translate(
            str.maketrans(
                {
                    "\u201c": '"',  # “
                    "\u201d": '"',  # ”
                    "\u2018": "'",  # ‘
                    "\u2019": "'",  # ’
                    "\uff0c": ",",  # ，
                    "\uff1a": ":",  # ：
                    "\uff1b": ";",  # ；
                }
            )
        )
        if text4 != text3:
            try:
                return json.loads(text4)
            except json.JSONDecodeError:
                pass

        # 第5层：单引号 → 双引号。
        # 仅替换"结构位置"的单引号（键名 + 非字符串标量），逐字符扫描避免
        # 误伤字符串内部的撇号（如英文 it's）。
        text5 = OpenaiClient._single_to_double_quote(text4)
        if text5 != text4:
            try:
                return json.loads(text5)
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _single_to_double_quote(text: str):
        """把 JSON 结构位置的单引号转成双引号，保留字符串内部的单引号。

        用状态机：区分"在字符串内"和"在结构位置"。结构位置的单引号
        （紧跟 key 或作为字符串边界）转双引号；字符串内的撇号保留。
        """
        out = []
        in_dq = False  # 是否在双引号字符串内
        in_sq = False  # 是否在单引号字符串内
        escape = False
        for ch in text:
            if escape:
                out.append(ch)
                escape = False
                continue
            if ch == "\\":
                out.append(ch)
                escape = True
                continue
            if in_dq:
                out.append(ch)
                if ch == '"':
                    in_dq = False
                continue
            if in_sq:
                if ch == "'":
                    out.append('"')
                    in_sq = False
                else:
                    out.append(ch)
                continue
            # 结构位置
            if ch == '"':
                in_dq = True
                out.append(ch)
            elif ch == "'":
                in_sq = True
                out.append('"')
            else:
                out.append(ch)
        return "".join(out)


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
