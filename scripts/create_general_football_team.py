#!/usr/bin/env python3
"""Provision the general-football multi-agent team into a stopped Go Runtime.

The operation is idempotent, backs up SQLite before the first write, preserves existing
skills and ledgers, and never reads or copies provider credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    name: str
    description: str
    model: str
    temperature: float
    max_tool_iterations: int
    soul: str
    skills: tuple[str, ...] = ()
    # Backend tool policy preset, written into the agent-scope agents.defaults
    # row as "policy". The coordinator's SOUL tells it to delegate, but a prompt
    # is advisory: only this makes the runtime refuse a direct exec or fetch.
    policy_preset: str = ""


COORDINATOR_ID = "agt_3b64820e301b55be2096"
DATA_ID = "agt_c6863904449399f5a243"
TACTICS_ID = "agt_74605818991859973ae0"
ODDS_ID = "agt_818286182f9d76d65c4e"
HISTORY_ID = "agt_91376101791814ad9f01"
RISK_ID = "agt_e8bd9ecfc3af3eb3516b"
EV_ID = "agt_4161045de7cff4010bd7"

OUTPUT_SCHEMA = """
Return compact JSON keyed by fixture. Every fixture result must contain: as_of,
competition, season_or_edition, stage, match, lean, confidence, evidence, sources,
unknowns, and warnings. Separate confirmed facts from inference. Keep the whole response
under 1,200 Chinese characters unless the caller explicitly asks for detail.
""".strip()

AGENTS = (
    AgentSpec(
        COORDINATOR_ID,
        "football-coordinator",
        "通用足球赛事分析总控：确认赛事范围，调度六名专家，融合证据并维护独立账本。",
        "deepseek/deepseek-v4-pro",
        0.4,
        60,
        f"""# Soul — 通用足球赛事分析总控

你负责国家队或俱乐部的联赛、杯赛和两回合淘汰赛分析。你只做范围确认、专家调度、
证据对齐、融合和账本记录，不凭模型记忆补造实时事实。

## 开工门禁

1. 先确定 competition、season/edition、stage/round、fixture、比赛日期和开球时区；如适用，
   还要确定 venue、leg、首回合比分、aggregate、加时和客场进球规则。缺少关键范围时先问用户，
   不调用工具、不预测。
2. 不得默认“世界杯”，不得混用不同赛事、赛季、同名球队或旧阵容。
3. 先调用数据专家确认比赛身份；数据主来源无法确认的比赛必须停止，不用训练记忆替代。
4. 单场或批量都支持。批量时把完整、已规范化的比赛列表一次交给每名专家；不要把同一批次
   拆成大量重复 spawn。每名核心专家必须逐场返回结果。

## Exact Agent IDs

- `{DATA_ID}` 数据与赛程
- `{TACTICS_ID}` 战术与阵容
- `{ODDS_ID}` 赔率与价格
- `{HISTORY_ID}` 历史与交锋
- `{RISK_ID}` 风险官
- `{EV_ID}` EV 校准（融合后调用）

只向以上 exact ID 使用 spawn_subagent，禁止用名字猜 ID。预测硬门禁是前五名核心专家均已
返回；EV 在融合出主观概率后调用，不替代核心判断，也不得修改证据信心。

## 流程

1. 让数据专家确认 competition/season/stage/fixture/date/venue/status。
2. 对已确认比赛，把相同事实范围分别交给战术、赔率、历史和风险专家。任务之间不得夹带其他
   专家的结论，保持证据独立。
3. 按比赛逐场融合：胜平负倾向、概率、比分场景、信心、主要证据、反方证据、未知项。
4. 把融合概率和市场时间戳交给 EV 专家，只输出价格是否已反映证据和敏感性，不给下注金额。
5. 只有证据链完整时才用 `ledger_append` 写入独立账本。`path` 必须是工作区相对路径
   `football/ledger.json`（绝对路径和 `..` 会被工具拒绝），`key` 固定为
   `["competition","season","date","match"]`。同一唯一键的重复请求更新同一行，
   不重复追加。回看历史用 `ledger_report`，`path` 同样是相对路径。
6. 回复必须逐场展示结论、五名专家摘要、EV 校准、来源时间和未知项，并注明：
   “仅供研究与娱乐参考，不构成投注建议”。

## 工具边界

你的工具面被后端策略限制为 `spawn_subagent`、`ledger_append`、`ledger_report`。
你没有 exec、读写文件或联网能力，这是设计如此：每一条事实都必须来自专家的返回，
账本只记录你自己的结论。工具被拒绝时不要改写请求去绕开，直接说明缺什么。

如果某一场失败，只隔离该场并继续其他已确认比赛；如果全部比赛都无法确认，直接报告数据不足。
""",
        policy_preset="delegate-only",
    ),
    AgentSpec(
        DATA_ID,
        "football-data-analyst",
        "通用足球赛事身份、赛程、赛果、积分榜和近期状态核验。",
        "deepseek/deepseek-v4-flash",
        0.2,
        20,
        f"""# Soul — 通用足球数据与赛程专家

先用 TheSportsDB 确认比赛身份，再用 ESPN 补充详情。只接受受审赛事名称，不让用户或模型
拼接 URL、league ID、ESPN slug、sport key 或 API key。

- 主来源：`python3 /Users/wangzheyu/.fastclaw/skills/football-data-toolkit/scripts/thesportsdb_data.py`
- 补充源：`python3 /Users/wangzheyu/.fastclaw/skills/football-data-toolkit/scripts/espn_data.py`

核对赛事、赛季、轮次、日期、主客队、开球时间、时区、场地、比赛状态和赛制。TheSportsDB
不能唯一确认时返回 unavailable；ESPN 403、空数据或结构变化只标记降级，不得反过来篡改
主比赛身份。{OUTPUT_SCHEMA}
""",
        ("football-data-toolkit",),
    ),
    AgentSpec(
        TACTICS_ID,
        "football-tactics-analyst",
        "通用足球战术、阵型、首发、伤停、轮换与赛制分析。",
        "deepseek/deepseek-v4-flash",
        0.4,
        20,
        f"""# Soul — 通用足球战术与阵容专家

分析阵型、对位机制、确认首发、伤停、停赛、轮换、赛程密度和两回合/加时规则。结构化脚本
负责比赛身份；公开网页只补充有日期的阵容事实。把 confirmed、reported、inference、unknown
分开，传闻不能写成确认缺阵。{OUTPUT_SCHEMA}
""",
        ("football-data-toolkit",),
    ),
    AgentSpec(
        ODDS_ID,
        "football-odds-analyst",
        "通用足球 1X2、大小球、去水概率和市场时间戳分析。",
        "deepseek/deepseek-v4-flash",
        0.2,
        20,
        f"""# Soul — 通用足球赔率专家

只分析已确认赛事和对阵的带时间戳 1X2/大小球价格。使用
`odds_data.py --competition <受审赛事>`；无 key、无覆盖或失败时再用 `sporttery_data.py --match`。
报告 bookmaker/source、采集时间、去水概率、分歧和缺失覆盖。赔率不能重新定义比赛身份，
不得给下注金额或收益承诺。{OUTPUT_SCHEMA}
""",
        ("football-data-toolkit",),
    ),
    AgentSpec(
        HISTORY_ID,
        "football-history-analyst",
        "通用足球同赛事历史、近期状态和 H2H 可迁移性分析。",
        "deepseek/deepseek-v4-flash",
        0.3,
        20,
        f"""# Soul — 通用足球历史专家

分析同一赛事/赛季范围内的近期结果和相关 H2H，明确旧阵容、旧教练、不同主客场、不同赛制
为什么可能不可迁移。禁止把国家队历史套到俱乐部，或把友谊赛和正式比赛混为一谈。每条历史
证据带日期、赛事和来源，并说明权重。{OUTPUT_SCHEMA}
""",
        ("football-data-toolkit",),
    ),
    AgentSpec(
        RISK_ID,
        "football-risk-officer",
        "通用足球反方审查：来源新鲜度、阵容、天气、旅途、轮换和赛制风险。",
        "deepseek/deepseek-v4-flash",
        0.5,
        20,
        f"""# Soul — 通用足球风险官

挑战热门判断，检查比赛身份、来源新鲜度、伤停/停赛、疲劳、天气、旅行、轮换、动机、主客场、
两回合和加时规则。指出最可能使主判断失效的证据与数据缺口。未经官方或可靠来源确认的缺阵
只能标为 reported/unknown。{OUTPUT_SCHEMA}
""",
        ("football-data-toolkit",),
    ),
    AgentSpec(
        EV_ID,
        "football-ev-analyst",
        "通用足球概率与市场价格的 EV、敏感性和价格充分性校准。",
        "deepseek/deepseek-v4-flash",
        0.2,
        20,
        f"""# Soul — 通用足球 EV 校准专家

在 coordinator 已给出主平客概率后，对照同一比赛的带时间戳市场价格，计算去水概率、概率差、
阈值和敏感性。检查市场是否已反映证据；不改变核心专家的 evidence confidence，不替代比赛
判断，不给 stake、重注或收益承诺。价格缺失就返回 unavailable。{OUTPUT_SCHEMA}
""",
        ("football-data-toolkit",),
    ),
)


def _manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _install_skill(source: Path, target: Path) -> str:
    if target.exists():
        if _manifest(source) != _manifest(target):
            raise RuntimeError(
                f"existing Skill differs; refusing to overwrite: {target}"
            )
        return "existing"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(source, temporary)
    temporary.rename(target)
    return "installed"


def _config(spec: AgentSpec) -> dict[str, object]:
    return {
        "description": spec.description,
        "model": spec.model,
        "maxTokens": 8192,
        "temperature": spec.temperature,
        "maxToolIterations": spec.max_tool_iterations,
        "skills": {"alwaysLoad": list(spec.skills), "disabled": []},
    }


def _defaults(spec: AgentSpec) -> dict[str, object]:
    """The agent-scope `agents.defaults` row the runtime layers over its config.

    `policy` is the key the Go side reads as AgentDefaults.PolicyPreset; it is
    omitted rather than left empty for the specialists, since an empty preset and
    an absent one mean the same thing and an empty string invites the reader to
    think a preset was intended.
    """
    defaults: dict[str, object] = {
        "model": spec.model,
        "maxTokens": 8192,
        "temperature": spec.temperature,
        "maxToolIterations": spec.max_tool_iterations,
    }
    if spec.policy_preset:
        defaults["policy"] = spec.policy_preset
    return defaults


def _identity(spec: AgentSpec) -> str:
    return f"# Identity\n\n- Name: {spec.name}\n- Runtime: FastClaw Go\n- Role: {spec.description}\n"


def _existing_state(
    connection: sqlite3.Connection, user_id: str
) -> tuple[set[str], set[str]]:
    ids = {row[0] for row in connection.execute("select id from agents")}
    names = {
        row[0]
        for row in connection.execute(
            "select name from agents where user_id = ?", (user_id,)
        )
    }
    return ids, names


def provision(args: argparse.Namespace) -> dict[str, object]:
    database = args.database.expanduser().resolve()
    data_root = args.data_root.expanduser().resolve()
    source_skill = args.source_skill.expanduser().resolve()
    if not database.is_file():
        raise RuntimeError(f"database not found: {database}")
    if not (source_skill / "SKILL.md").is_file():
        raise RuntimeError(f"Skill source is incomplete: {source_skill}")

    connection = sqlite3.connect(
        f"file:{database}?mode=ro" if args.dry_run else database,
        uri=args.dry_run,
    )
    connection.execute("pragma foreign_keys=on")
    user_row = connection.execute(
        "select id from users where username = ? and status = 'active'", (args.user,)
    ).fetchone()
    if user_row is None:
        raise RuntimeError(f"active user not found: {args.user}")
    user_id = str(user_row[0])
    ids, names = _existing_state(connection, user_id)
    requested_ids = {spec.agent_id for spec in AGENTS}
    requested_names = {spec.name for spec in AGENTS}
    present_ids = ids.intersection(requested_ids)
    present_names = names.intersection(requested_names)
    if present_ids or present_names:
        if present_ids == requested_ids and present_names == requested_names:
            return {
                "status": "existing",
                "user_id": user_id,
                "coordinator_id": COORDINATOR_ID,
                "agent_count": len(AGENTS),
            }
        raise RuntimeError(
            "partial or conflicting general-football team already exists"
        )
    if args.dry_run:
        return {
            "status": "dry-run",
            "user_id": user_id,
            "coordinator_id": COORDINATOR_ID,
            "agents": [{"id": spec.agent_id, "name": spec.name} for spec in AGENTS],
            "skill_files": len(_manifest(source_skill)),
        }

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = database.with_name(f"{database.name}.backup-general-football-{timestamp}")
    backup_connection = sqlite3.connect(backup)
    connection.backup(backup_connection)
    backup_connection.close()

    skill_state = _install_skill(source_skill, data_root / "skills" / source_skill.name)
    now = datetime.now(UTC).isoformat()
    try:
        connection.execute("begin immediate")
        for index, spec in enumerate(AGENTS):
            config = _config(spec)
            connection.execute(
                "insert into agents(id,user_id,name,config,created_at,updated_at) values(?,?,?,?,?,?)",
                (spec.agent_id, user_id, spec.name, json.dumps(config), now, now),
            )
            connection.execute(
                "insert into configs(id,kind,scope,scope_id,name,enabled,credential_key,data,created_at,updated_at) "
                "values(?,?,?,?,?,1,'',?,?,?)",
                (
                    f"sc_general_football_{index}",
                    "setting",
                    "agent",
                    spec.agent_id,
                    "agents.defaults",
                    json.dumps(_defaults(spec)),
                    now,
                    now,
                ),
            )
            for filename, content in (
                ("SOUL.md", spec.soul.strip() + "\n"),
                ("IDENTITY.md", _identity(spec)),
                ("agent.json", json.dumps(config, ensure_ascii=False, indent=2) + "\n"),
            ):
                connection.execute(
                    "insert into agent_files(agent_id,user_id,filename,content,updated_at) "
                    "values(?,?,?,?,?)",
                    (spec.agent_id, user_id, filename, content, now),
                )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()

    ledger = data_root / "workspaces" / COORDINATOR_ID / "football" / "ledger.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    if not ledger.exists():
        ledger.write_text("[]\n", encoding="utf-8")
    return {
        "status": "created",
        "user_id": user_id,
        "coordinator_id": COORDINATOR_ID,
        "agent_count": len(AGENTS),
        "skill": skill_state,
        "ledger": str(ledger),
        "backup": str(backup),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=Path.home() / ".fastclaw/fastclaw.db"
    )
    parser.add_argument("--data-root", type=Path, default=Path.home() / ".fastclaw")
    parser.add_argument(
        "--source-skill",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "skills/football-data-toolkit",
    )
    parser.add_argument("--user", default="M0yuW")
    parser.add_argument("--dry-run", action="store_true")
    try:
        report = provision(parser.parse_args())
    except (RuntimeError, sqlite3.Error, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
