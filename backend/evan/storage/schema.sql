CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    pgn_text TEXT NOT NULL,
    fen_root TEXT NOT NULL,
    has_full_history INTEGER NOT NULL DEFAULT 1,
    white TEXT NOT NULL DEFAULT 'White',
    black TEXT NOT NULL DEFAULT 'Black',
    result TEXT NOT NULL DEFAULT '*',
    event TEXT NOT NULL DEFAULT '',
    player_color TEXT NOT NULL DEFAULT 'white',
    target_rating INTEGER NOT NULL DEFAULT 1500,
    platform TEXT NOT NULL DEFAULT 'lichess',
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    critical_plies_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    untrusted_comments_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS ply_analyses (
    game_id TEXT NOT NULL,
    ply INTEGER NOT NULL,
    move_number INTEGER NOT NULL,
    turn TEXT NOT NULL,
    uci_move TEXT NOT NULL,
    san_move TEXT NOT NULL,
    fen_before TEXT NOT NULL,
    fen_after TEXT NOT NULL,
    state_before_hash TEXT NOT NULL,
    state_after_hash TEXT NOT NULL,
    coarse_eval_cp_white INTEGER,
    coarse_mate_white INTEGER,
    coarse_eval_after_cp_white INTEGER,
    coarse_mate_after_white INTEGER,
    eval_swing_cp INTEGER NOT NULL DEFAULT 0,
    critical_score REAL NOT NULL DEFAULT 0.0,
    critical_reason_json TEXT NOT NULL DEFAULT '{}',
    is_critical INTEGER NOT NULL DEFAULT 0,
    deep_status TEXT NOT NULL DEFAULT 'queued',
    priority_boost INTEGER NOT NULL DEFAULT 0,
    ledger_json TEXT,
    commentary_json TEXT,
    PRIMARY KEY (game_id, ply),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS engine_cache (
    cache_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    record_json TEXT NOT NULL
);
