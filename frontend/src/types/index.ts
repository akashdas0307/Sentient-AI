export interface EventMessage {
  type: "event";
  stage: string;
  event_name: string;
  data: Record<string, unknown>;
  turn_id: string | null;
  timestamp: number;
}

export interface TurnRecord {
  turn_id: string;
  user_message: string;
  assistant_reply: string;
  events: EventMessage[];
  started_at: number;
  completed_at: number | null;
  is_complete: boolean;
}

export interface HealthSnapshot {
  [module: string]: {
    latest: { status: string };
    pulse_count: number;
    status: string;
  };
}

export type WSMessageType = "health" | "welcome" | "event" | "reply" | "pong";

export interface WSMessage {
  type: WSMessageType;
  timestamp: number;
  data?: any;
  payload?: any; // Some routes use payload, some use data
  health?: HealthSnapshot;
  event?: EventMessage;
  turn?: TurnRecord;
  text?: string;
}

export interface SystemStatus {
  status: string;
  version: string;
  uptime: number;
  modules: string[];
}

export interface MemoryStats {
  count: number;
}
