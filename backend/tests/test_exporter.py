import io

import chess.pgn

from evan.chess_core.parser import parse_game_input
from evan.export.pgn_exporter import export_annotated_pgn, export_ledger


def test_annotated_pgn_preserves_mainline_and_citations():
    pgn = export_annotated_pgn(
        {"pgn_text": "1. e4 e5 2. Nf3 Nc6 *"},
        [
            {
                "ply": 0,
                "uci_move": "e2e4",
                "commentary": {
                    "sentences": [{"text": "At this budget, e4 is preferred.", "claim_ids": ["claim1"]}]
                },
                "ledger": {
                    "branch_bundle": {
                        "branches": [
                            {"branch_id": "alternative", "primary_record": {"pv_uci": ["d2d4", "d7d5"]}}
                        ]
                    }
                },
            }
        ],
    )
    parsed = chess.pgn.read_game(io.StringIO(pgn))
    assert parsed is not None
    assert [move.uci() for move in parsed.mainline_moves()] == ["e2e4", "e7e5", "g1f3", "b8c6"]
    assert '%evan_claim_ids "claim1"' in pgn
    assert [move.uci() for move in parsed.variations[1].mainline_moves()] == ["d7d5"]
    assert parsed.variations[1].move.uci() == "d2d4"


def test_exports_exclude_untrusted_comments_and_sanitize_braces():
    ledger = export_ledger({"pgn_text": "1. e4 *", "untrusted_comments": {0: "injected"}}, [])
    assert "untrusted_comments" not in ledger["game"]
    assert ledger["limitations"]
    pgn = export_annotated_pgn(
        {"pgn_text": "1. e4 *", "untrusted_comments": {0: "injected"}},
        [{"ply": 0, "uci_move": "e2e4", "commentary": {"sentences": [], "abstention_notice": "No evidence {untrusted}"}}],
    )
    assert "injected" not in pgn
    assert "{untrusted}" not in pgn
    assert "EVAN abstention" in pgn


def test_export_pgn_preserves_escaped_header_quotes():
    parsed_in = parse_game_input('[Event "A \\"quoted\\" name\\\\test"]\n\n1. e4 e5 *')
    pgn = export_annotated_pgn({"pgn_text": parsed_in.clean_pgn}, [])
    reparsed = parse_game_input(pgn)
    assert reparsed.event == 'A "quoted" name\\test'
