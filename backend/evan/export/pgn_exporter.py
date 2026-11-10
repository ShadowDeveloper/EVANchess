from __future__ import annotations

import io
import re
from typing import Any

import chess
import chess.pgn

from evan.chess_core.parser import serialize_pgn


def _safe_comment(text: str) -> str:
    return re.sub(r"[{}\x00-\x1f]", " ", text)


def export_annotated_pgn(game: dict[str, Any], plies: list[dict[str, Any]]) -> str:
    parsed = chess.pgn.read_game(io.StringIO(game["pgn_text"]))
    if parsed is None:
        raise ValueError("Stored game could not be read.")
    for key, value in list(parsed.headers.items()):
        parsed.headers[key] = re.sub(r'\\(["\\])', r"\1", value)
    nodes = list(parsed.mainline())
    for row in plies:
        node = nodes[row["ply"]] if row["ply"] < len(nodes) else parsed
        commentary = row.get("commentary") or {}
        sentences = commentary.get("sentences", [])
        text = " ".join(sentence["text"] for sentence in sentences)
        if commentary.get("abstention_notice"):
            text += " EVAN abstention: " + commentary["abstention_notice"]
        ids = sorted({claim for sentence in sentences for claim in sentence.get("claim_ids", [])})
        if text:
            node.comment = _safe_comment(text) + (' [%evan_claim_ids "' + ",".join(ids) + '"]' if ids else "")
        ledger = row.get("ledger") or {}
        bundle = ledger.get("branch_bundle") or {}
        for branch in bundle.get("branches", []):
            pv = branch.get("primary_record", {}).get("pv_uci", [])
            parent = node.parent if node.parent else parsed
            board = parent.board()
            if not pv or pv[0] == row["uci_move"]:
                continue
            current = parent
            for uci in pv[:8]:
                move = chess.Move.from_uci(uci)
                if move not in board.legal_moves:
                    break
                current = current.add_variation(move)
                board.push(move)
            current.comment = _safe_comment("EVAN conditional engine variation: " + branch["branch_id"])
    return serialize_pgn(parsed)


def export_ledger(game: dict[str, Any], plies: list[dict[str, Any]]) -> dict[str, Any]:
    clean_game = {key: value for key, value in game.items() if key != "untrusted_comments"}
    return {"schema_version": "0.1.0", "game": clean_game, "plies": plies,
            "limitations": ["Engine variations are conditional examples, not exhaustive proof trees.",
                             "Passing automated prose checks does not certify all natural-language implications.",
                             "Optional Maia, Lc0 and tablebase interfaces are not enabled integrations."]}
