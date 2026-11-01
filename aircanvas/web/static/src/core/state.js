'use strict';

import { DEFAULT_CONFIG } from './constants.js';
import { clone } from './utils.js';

/** One reactive-ish store, shared by the controllers and renderers. */
export const state = {
  config: clone(DEFAULT_CONFIG),
  snapshot: null,
  connected: false,
  configured: false,
  lastSeq: 0,
  ws: null,
  reconnectTimer: null,
  reconnectDelay: 900,
  features: {},
  demo: false,
  demoImage: null,
  demoSeq: 0,
  wantDemo: false,
  demoSeek: 0,
  demoStarted: false,
  cameraStream: null,
  cameraStatus: 'off',
  cameraError: '',
  cameraDeviceId: '',
  captureTimer: null,
  manualOnly: false,
  startPanelDismissed: false,
  seenEventIds: new Set(),
  ripples: [],
  trail: [],
  lastPointer: null,
  lastTrackFingerprint: '',
  lastToast: '',
  toastTimer: null,
  pendingConfig: {},
  configTimer: null,
  frameInFlight: false,
  skipIntro: false,
  autoDemo: false,
  autoDemoSeek: 0,
  urlMode: null,
  urlTool: null,
  leftHanded: false,
};

export function activeTool() {
  return state.config.mode === 'mirror' ? state.config.mirror_tool : state.config.tool;
}
