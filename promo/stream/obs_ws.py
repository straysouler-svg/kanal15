"""Подключение к OBS по websocket (obs-websocket 5.x).

Сервер включён в OBS: Инструменты -> WebSocket Server Settings.
Порт и пароль лежат в %APPDATA%/obs-studio/plugin_config/obs-websocket/config.json.

Пример:
    from obs_ws import ObsWs
    with ObsWs() as ws:
        print(ws.call('GetCurrentProgramScene'))

Вертикальный канвас (Aitum Vertical) изолирован от основного:
для его сцен во все запросы добавлять canvasUuid=VERT_CANVAS_UUID,
а источники в нём — отдельные объекты (свой «Микрофон (Верт: В пути)»).
"""

import base64
import hashlib
import json
import os

import websocket

CONFIG = os.path.join(
    os.environ['APPDATA'], 'obs-studio', 'plugin_config', 'obs-websocket', 'config.json'
)
VERT_CANVAS_UUID = 'cc388a46-84fc-4937-a2b9-18e0f051612f'  # Aitum Vertical


class ObsWs:
    def __init__(self):
        cfg = json.load(open(CONFIG, encoding='utf-8'))
        if not cfg.get('server_enabled'):
            raise RuntimeError('websocket-сервер выключен в настройках OBS')
        self.ws = websocket.create_connection(
            f"ws://127.0.0.1:{cfg.get('server_port', 4455)}", timeout=10
        )
        hello = json.loads(self.ws.recv())
        auth = hello['d'].get('authentication')
        payload = {}
        if auth:
            secret = base64.b64encode(
                hashlib.sha256((cfg['server_password'] + auth['salt']).encode()).digest()
            )
            payload['authentication'] = base64.b64encode(
                hashlib.sha256(secret + auth['challenge'].encode()).digest()
            ).decode()
        self.ws.send(json.dumps({'op': 1, 'd': {'rpcVersion': 1, **payload}}))
        json.loads(self.ws.recv())
        self._rid = 0

    def call(self, method, data=None):
        self._rid += 1
        self.ws.send(json.dumps({'op': 6, 'd': {
            'requestType': method, 'requestId': str(self._rid),
            'requestData': data or {},
        }}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get('op') == 7 and r['d']['requestId'] == str(self._rid):
                st = r['d']['requestStatus']
                if not st['result']:
                    raise RuntimeError(f"{method}: {st.get('code')} {st.get('comment')}")
                return r['d'].get('responseData') or {}

    def close(self):
        self.ws.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
