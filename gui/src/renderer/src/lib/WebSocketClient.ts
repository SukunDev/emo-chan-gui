/* eslint-disable @typescript-eslint/no-explicit-any */
// src/lib/websocket/WebSocketClient.ts

export type WSListener = (data: any) => void;

export default class WebSocketClient {
  private url: string;
  private socket: WebSocket | null = null;
  private listeners: Map<string, WSListener[]> = new Map();
  private reconnectDelay = 2000;

  constructor(url: string) {
    this.url = url;
  }

  connect():void {
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      console.log("[WS] Connected");
      this.emitLocal("open", null);
    };

    this.socket.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        this.emitLocal("message", data);
      } catch {
        this.emitLocal("message", msg.data);
      }
    };

    this.socket.onclose = () => {
      console.log("[WS] Disconnected, retrying...");
      this.emitLocal("close", null);
      setTimeout(() => this.connect(), this.reconnectDelay);
    };
  }

  send(data: any):void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn("[WS] Cannot send, socket not open");
      return;
    }
    this.socket.send(JSON.stringify(data));
  }

  on(event: "open" | "message" | "close", callback: WSListener):void {
    if (!this.listeners.has(event)) this.listeners.set(event, []);
    this.listeners.get(event)!.push(callback);
  }

  private emitLocal(event: string, data: any):void {
    const callbacks = this.listeners.get(event);
    if (callbacks) callbacks.forEach((cb) => cb(data));
  }
}
