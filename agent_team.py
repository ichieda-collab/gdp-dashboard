"""
GDP Dashboard Agent Team
========================
エージェントチームを使ってGDPデータを分析し、洞察レポートを生成するスクリプト。

チーム構成:
- オーケストレーター: タスクを調整し各専門エージェントに割り当てる
- データアナリスト: GDPデータを読み込んで統計的な分析を行う
- リサーチャー: 経済的な文脈・背景情報をウェブで調査する
- レポートライター: 分析結果をまとめて最終レポートを作成する

使い方:
    python agent_team.py
    python agent_team.py --countries JPN USA CHN --years 2000 2022
"""

import anyio
import argparse
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, ResultMessage, SystemMessage


def build_agent_team(countries: list[str], from_year: int, to_year: int) -> ClaudeAgentOptions:
    """エージェントチームのオプションを構築する。"""

    data_analyst = AgentDefinition(
        description="GDPデータファイルを読み込んで統計分析を行う専門家",
        prompt=(
            "あなたはGDP経済データの専門アナリストです。"
            "data/gdp_data.csv を読み込み、指定された国と期間のデータを抽出・分析してください。"
            "平均成長率、最大値・最小値、トレンドなどの統計を算出してください。"
            "分析結果は具体的な数値を含む日本語で報告してください。"
        ),
        tools=["Read", "Glob", "Bash"],
    )

    researcher = AgentDefinition(
        description="経済的な文脈・背景情報をウェブで調査する専門家",
        prompt=(
            "あなたは国際経済の専門リサーチャーです。"
            "指定された国々のGDP成長に関連する歴史的・経済的な背景を調査してください。"
            "主要な経済イベント、政策転換、グローバルな影響などを調べてください。"
            "調査結果は分かりやすい日本語でまとめてください。"
        ),
        tools=["WebSearch", "WebFetch"],
    )

    report_writer = AgentDefinition(
        description="分析結果をまとめて読みやすいレポートを作成する専門家",
        prompt=(
            "あなたはビジネスレポートの専門ライターです。"
            "データアナリストとリサーチャーから得た情報をもとに、"
            "経営者や一般読者向けの分かりやすいGDP分析レポートを日本語で作成してください。"
            "レポートには以下のセクションを含めてください:\n"
            "1. エグゼクティブサマリー\n"
            "2. 主要な発見\n"
            "3. 国別の詳細分析\n"
            "4. 今後の展望\n"
            "レポートはファイルに保存してください。"
        ),
        tools=["Read", "Write"],
    )

    orchestrator_prompt = f"""
あなたはGDP分析プロジェクトのオーケストレーターです。
以下のエージェントチームを活用して、包括的なGDP分析レポートを作成してください。

分析対象:
- 国コード: {', '.join(countries)}
- 期間: {from_year}年〜{to_year}年
- データファイル: data/gdp_data.csv

実行手順:
1. data-analyst エージェントに指定国・期間のGDPデータ分析を依頼する
2. researcher エージェントに各国の経済的背景の調査を依頼する
3. report-writer エージェントに分析・調査結果をもとにレポート作成を依頼する
   - レポートは gdp_report.md として保存すること
4. 最終的なレポートの内容を要約して報告する

必ず3つのエージェントを順番に使用してください。
"""

    return ClaudeAgentOptions(
        cwd="/home/user/gdp-dashboard",
        allowed_tools=["Read", "Glob", "Bash", "WebSearch", "WebFetch", "Write", "Agent"],
        permission_mode="acceptEdits",
        max_turns=30,
        agents={
            "data-analyst": data_analyst,
            "researcher": researcher,
            "report-writer": report_writer,
        },
        system_prompt=orchestrator_prompt,
    )


async def run_agent_team(countries: list[str], from_year: int, to_year: int) -> None:
    """エージェントチームを実行してGDP分析レポートを生成する。"""

    print(f"\n=== GDP エージェントチーム起動 ===")
    print(f"対象国: {', '.join(countries)}")
    print(f"期間: {from_year}〜{to_year}年")
    print("=" * 40)

    options = build_agent_team(countries, from_year, to_year)

    prompt = (
        f"{', '.join(countries)} の {from_year}〜{to_year}年のGDPデータを分析し、"
        "エージェントチームを使って包括的なレポートを作成してください。"
    )

    session_id = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            session_id = message.data.get("session_id")
            print(f"セッションID: {session_id}\n")
        elif isinstance(message, ResultMessage):
            print("\n=== 最終結果 ===")
            print(message.result)
            print(f"\n停止理由: {message.stop_reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GDP エージェントチーム分析ツール")
    parser.add_argument(
        "--countries",
        nargs="+",
        default=["JPN", "USA", "CHN", "DEU"],
        help="分析する国コード (例: JPN USA CHN)",
    )
    parser.add_argument(
        "--years",
        nargs=2,
        type=int,
        default=[2000, 2022],
        metavar=("FROM", "TO"),
        help="分析期間 (例: 2000 2022)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    anyio.run(run_agent_team, args.countries, args.years[0], args.years[1])
