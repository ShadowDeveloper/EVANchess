import type {
  GameDetail,
  GameSummary,
  HealthResponse,
  ImportGamePayload,
  RemotePlatformGame,
} from '../types/evan';

const API_BASE = '/api';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string | { msg?: string }[];
      message?: string;
      error?: string;
    };
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      return data.detail.map((item) => item.msg || JSON.stringify(item)).join('; ');
    }
    if (data.message) {
      return data.message;
    }
    if (data.error) {
      return data.error;
    }
  } catch {
    void 0;
  }
  return `Request failed with HTTP ${response.status}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    throw new ApiError(
      err instanceof Error ? err.message : 'Unable to reach EVAN backend server.',
      0,
    );
  }

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health');
}

export async function fetchGames(): Promise<GameSummary[]> {
  return requestJson<GameSummary[]>('/games');
}

export async function fetchGameDetail(gameId: string): Promise<GameDetail> {
  return requestJson<GameDetail>(`/games/${encodeURIComponent(gameId)}`);
}

export async function importGame(payload: ImportGamePayload): Promise<GameDetail> {
  return requestJson<GameDetail>('/games/import', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchUserRecentGames(
  platform: 'lichess' | 'chesscom',
  username: string,
  maxGames = 10,
): Promise<RemotePlatformGame[]> {
  const encodedUser = encodeURIComponent(username.trim());
  return requestJson<RemotePlatformGame[]>(
    `/importers/${platform}/${encodedUser}?max_games=${maxGames}`,
  );
}

export async function prioritizePlyAnalysis(
  gameId: string,
  ply: number,
): Promise<{ status?: string; prioritized?: boolean; game?: GameDetail }> {
  return requestJson<{ status?: string; prioritized?: boolean; game?: GameDetail }>(
    `/games/${encodeURIComponent(gameId)}/plies/${ply}/prioritize`,
    {
      method: 'POST',
    },
  );
}

export function getExportPgnUrl(gameId: string): string {
  return `${API_BASE}/games/${encodeURIComponent(gameId)}/export/pgn`;
}

export function getExportLedgerUrl(gameId: string): string {
  return `${API_BASE}/games/${encodeURIComponent(gameId)}/export/ledger`;
}

export async function downloadExportFile(
  url: string,
  fallbackFilename: string,
): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) {
    const msg = await parseErrorMessage(response);
    throw new ApiError(msg, response.status);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = fallbackFilename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}

export interface GameEventsSubscriptionCallbacks {
  onSnapshot: (game: GameDetail) => void;
  onComplete?: (game?: GameDetail) => void;
  onError?: (message: string) => void;
}

export function subscribeToGameEvents(
  gameId: string,
  callbacks: GameEventsSubscriptionCallbacks,
): () => void {
  if (typeof EventSource === 'undefined') {
    return () => {};
  }

  const url = `${API_BASE}/games/${encodeURIComponent(gameId)}/events`;
  const source = new EventSource(url);

  const handlePayload = (rawData: string, isCompleteEvent = false) => {
    if (!rawData) {
      if (isCompleteEvent) {
        callbacks.onComplete?.();
      }
      return;
    }
    try {
      const parsed = JSON.parse(rawData) as
        | GameDetail
        | { game?: GameDetail; detail?: string; error?: string; status?: string };
      if ('game_id' in parsed && Array.isArray(parsed.plies)) {
        callbacks.onSnapshot(parsed);
        if (isCompleteEvent) {
          callbacks.onComplete?.(parsed);
        }
      } else if ('game' in parsed && parsed.game && 'game_id' in parsed.game) {
        callbacks.onSnapshot(parsed.game);
        if (isCompleteEvent) {
          callbacks.onComplete?.(parsed.game);
        }
      } else if (isCompleteEvent) {
        callbacks.onComplete?.();
      }
    } catch {
      if (isCompleteEvent) {
        callbacks.onComplete?.();
      }
    }
  };

  source.addEventListener('snapshot', (event: MessageEvent<string>) => {
    handlePayload(event.data, false);
  });

  source.addEventListener('moment_ready', (event: MessageEvent<string>) => {
    handlePayload(event.data, false);
  });

  source.addEventListener('complete', (event: MessageEvent<string>) => {
    handlePayload(event.data, true);
    source.close();
  });

  source.addEventListener('error', (event: Event) => {
    const msgEvent = event as MessageEvent<string>;
    if (typeof msgEvent.data === 'string' && msgEvent.data.trim()) {
      try {
        const parsed = JSON.parse(msgEvent.data) as { error?: string; detail?: string; message?: string };
        callbacks.onError?.(
          parsed.error || parsed.detail || parsed.message || 'Analysis stream error.',
        );
      } catch {
        callbacks.onError?.(msgEvent.data);
      }
      source.close();
    }
  });

  source.onmessage = (event: MessageEvent<string>) => {
    handlePayload(event.data, false);
  };

  return () => {
    source.close();
  };
}
