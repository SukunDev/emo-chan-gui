/* eslint-disable @typescript-eslint/explicit-function-return-type */
/* eslint-disable react-refresh/only-export-components */
/* eslint-disable @typescript-eslint/no-explicit-any */


import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import WebSocketClient from "@renderer/lib/WebSocketClient";

type WSContextType = {
  ws: WebSocketClient | null;
  lastMessage: any;
  send: (data: any) => void;
};

const WebSocketContext = createContext<WSContextType>({
  ws: null,
  lastMessage: null,
  send: () => {},
});

export const WebSocketProvider = ({
  url,
  children,
}: {
  url: string;
  children: React.ReactNode;
}) => {
  const wsRef = useRef<WebSocketClient | null>(null);
  const [lastMessage, setLastMessage] = useState<any>(null);

  useEffect(() => {
    const client = new WebSocketClient(url);
    wsRef.current = client;

    client.on("message", (msg) =>{
       setLastMessage(msg)
    });

    client.connect();

    return () => {
      // websockets auto close via browser
    };
  }, [url]);

  const send = (data: any) => {
    wsRef.current?.send(data);
  };

  return (
    <WebSocketContext.Provider
      value={{
        ws: wsRef.current,
        lastMessage,
        send,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => useContext(WebSocketContext);
