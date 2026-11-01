'use strict';

import { state } from './state.js';
import { toast } from './ui.js';

/** Transport bridge: all modules can send without importing the entrypoint. */
export function send(payload) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    toast('Local service is not connected yet. Trying to reconnect…', 'warning');
    return false;
  }
  state.ws.send(JSON.stringify(payload));
  return true;
}
