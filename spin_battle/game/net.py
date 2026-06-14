"""Локальная сеть (LAN) для битвы 1 на 1.

Простая модель «хост-авторитет»: хост считает физику и шлёт состояние, клиент
шлёт свой ввод и только отрисовывает. Поверх TCP строками JSON. Хост объявляет
себя по UDP-broadcast, чтобы клиент нашёл его на той же Wi-Fi без ввода IP.

Работает в фоне (потоки), игровой цикл не блокируется. Не предназначено для
интернета — только локальная сеть.
"""

from __future__ import annotations

import json
import socket
import threading
import time

DISCOVERY_PORT = 50505
MAGIC = "SPINBATTLE1"


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _send_line(conn, obj):
    conn.sendall((json.dumps(obj) + "\n").encode())


class HostNet:
    """Хост: ждёт клиента, обменивается конфигом, шлёт состояние, читает ввод."""

    def __init__(self, my_config):
        self.my_config = my_config
        self.peer_config = None
        self.connected = False
        self.error = None
        self.latest_input = {"dx": 0.0, "dy": 0.0, "boost": False}
        self.ip = get_lan_ip()
        self.port = 0
        self._conn = None
        self._run = True
        threading.Thread(target=self._serve, daemon=True).start()
        threading.Thread(target=self._announce, daemon=True).start()

    def _serve(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", 0))
            self.port = srv.getsockname()[1]
            srv.listen(1)
            srv.settimeout(120)
            conn, _addr = srv.accept()
            self._conn = conn
            f = conn.makefile("rb")
            _send_line(conn, {"hello": self.my_config})
            line = f.readline()
            self.peer_config = json.loads(line.decode()).get("hello")
            self.connected = True
            while self._run:
                line = f.readline()
                if not line:
                    break
                try:
                    m = json.loads(line.decode())
                    if "in" in m:
                        self.latest_input = m["in"]
                except Exception:
                    pass
        except Exception as e:
            self.error = str(e)
        self.connected = False

    def _announce(self):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self._run and not self.connected:
            if self.port:
                payload = json.dumps({"magic": MAGIC, "port": self.port}).encode()
                try:
                    u.sendto(payload, ("255.255.255.255", DISCOVERY_PORT))
                except Exception:
                    pass
            time.sleep(0.5)
        u.close()

    def send_state(self, state):
        if self._conn:
            try:
                _send_line(self._conn, {"st": state})
            except Exception as e:
                self.error = str(e)
                self.connected = False

    def close(self):
        self._run = False
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass


class ClientNet:
    """Клиент: находит хост (или по адресу), шлёт ввод, читает состояние."""

    def __init__(self, my_config, host_addr=None):
        self.my_config = my_config
        self.peer_config = None
        self.connected = False
        self.error = None
        self.latest_state = None
        self._conn = None
        self._run = True
        threading.Thread(target=self._connect, args=(host_addr,),
                         daemon=True).start()

    def _discover(self):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            u.bind(("", DISCOVERY_PORT))
        except Exception as e:
            self.error = str(e)
            return None
        u.settimeout(15)
        try:
            data, addr = u.recvfrom(1024)
            m = json.loads(data.decode())
            if m.get("magic") == MAGIC:
                return (addr[0], m["port"])
        except Exception:
            self.error = "хост не найден"
        finally:
            u.close()
        return None

    def _connect(self, host_addr):
        try:
            if host_addr is None:
                host_addr = self._discover()
            if not host_addr:
                if not self.error:
                    self.error = "хост не найден"
                return
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.settimeout(10)
            c.connect(host_addr)
            c.settimeout(None)
            self._conn = c
            f = c.makefile("rb")
            line = f.readline()
            self.peer_config = json.loads(line.decode()).get("hello")
            _send_line(c, {"hello": self.my_config})
            self.connected = True
            while self._run:
                line = f.readline()
                if not line:
                    break
                try:
                    m = json.loads(line.decode())
                    if "st" in m:
                        self.latest_state = m["st"]
                except Exception:
                    pass
        except Exception as e:
            self.error = str(e)
        self.connected = False

    def send_input(self, inp):
        if self._conn:
            try:
                _send_line(self._conn, {"in": inp})
            except Exception as e:
                self.error = str(e)
                self.connected = False

    def close(self):
        self._run = False
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass
