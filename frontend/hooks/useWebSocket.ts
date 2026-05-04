"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type WsStatus = "connecting" | "connected" | "disconnected" | "error";

export interface WsMessage {
  type: string;
  payload: unknown;
  timestamp: string;
}

export interface UseWebSocketReturn {
  status: WsStatus;
  lastMessage: WsMessage | null;
  sendMessage: (msg: object) => void;
  reconnect: () => void;
}

const WS_URL = "ws://localhost:8000/ws";
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 5;

export function useWebSocket(): UseWebSocketReturn {
  const wsRef          = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef     = useRef(true);

  const [status, setStatus]           = useState<WsStatus>("disconnected");
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }
    if (!mountedRef.current) return;
    if (reconnectCount.current >= MAX_RECONNECT_ATTEMPTS) {
      setStatus("error");
      return;
    }
    setStatus("connecting");
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectCount.current = 0;
      setStatus("connected");
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        setLastMessage(JSON.parse(event.data as string));
      } catch {
        setLastMessage({ type: "raw", payload: event.data, timestamp: new Date().toISOString() });
      }
    };

    ws.onerror = () => setStatus("error");

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setStatus("disconnected");
      reconnectCount.current += 1;
      reconnectTimer.current = setTimeout(() => {
        if (mountedRef.current) connect();
      }, RECONNECT_DELAY_MS);
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    } else {
      console.warn("[WS] Not connected.");
    }
  }, []);

  const reconnect = useCallback(() => {
    reconnectCount.current = 0;
    connect();
  }, [connect]);

  return { status, lastMessage, sendMessage, reconnect };
}
