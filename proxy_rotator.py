#!/usr/bin/env python3
"""
Rotating Proxy Server
- Helyi HTTP proxy: 127.0.0.1:8080
- Minden kérésnél más upstream proxyt használ
- Automatikusan frissíti a proxy listát 10 percenként
- Állítsd be a böngésződben: Proxy = 127.0.0.1:8080
"""

import socket
import threading
import select
import requests
import time
import random
import logging
from concurrent.futures import ThreadPoolExecutor

# --- Konfiguráció ---
LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = 8080
PROXY_TIMEOUT = 6
REFRESH_INTERVAL = 600       # proxy lista frissítés 10 percenként
TEST_URL = 'http://httpbin.org/ip'
MAX_TEST = 400               # ennyi proxyt tesztelünk egyszerre
BUFFER_SIZE = 65536

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)


class ProxyPool:
    def __init__(self):
        self._proxies = []
        self._lock = threading.RLock()

    def _fetch_raw(self):
        sources = [
            'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=elite',
            'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
            'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt',
            'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
        ]
        seen = set()
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                for line in r.text.strip().splitlines():
                    p = line.strip().split()[0]  # csak ip:port rész
                    if ':' in p:
                        seen.add(p)
            except Exception as e:
                log.warning(f'Forrás nem elérhető: {url} — {e}')
        log.info(f'Összesen {len(seen)} nyers proxy letöltve')
        return list(seen)

    def _test(self, proxy_str):
        try:
            proxies = {
                'http': f'http://{proxy_str}',
                'https': f'http://{proxy_str}',
            }
            r = requests.get(TEST_URL, proxies=proxies, timeout=PROXY_TIMEOUT)
            if r.status_code == 200:
                ip = r.json().get('origin', '?')
                return proxy_str, ip
        except:
            pass
        return None, None

    def refresh(self):
        raw = self._fetch_raw()
        sample = random.sample(raw, min(len(raw), MAX_TEST))
        log.info(f'{len(sample)} proxy tesztelése folyamatban...')
        working = []
        with ThreadPoolExecutor(max_workers=80) as ex:
            for proxy, ip in ex.map(self._test, sample):
                if proxy:
                    working.append(proxy)
        log.info(f'Működő proxyk: {len(working)}')
        with self._lock:
            self._proxies = working

    def get_random(self):
        with self._lock:
            return random.choice(self._proxies) if self._proxies else None

    def remove(self, proxy):
        with self._lock:
            try:
                self._proxies.remove(proxy)
            except ValueError:
                pass

    def count(self):
        with self._lock:
            return len(self._proxies)


pool = ProxyPool()


def forward_traffic(src, dst):
    try:
        while True:
            ready, _, _ = select.select([src, dst], [], [], 15)
            if not ready:
                break
            for s in ready:
                data = s.recv(BUFFER_SIZE)
                if not data:
                    return
                other = dst if s is src else src
                other.sendall(data)
    except:
        pass


def handle_client(client_sock):
    upstream = None
    proxy = None
    try:
        data = client_sock.recv(BUFFER_SIZE)
        if not data:
            return

        first_line = data.split(b'\r\n')[0].decode(errors='replace')
        parts = first_line.split()
        if len(parts) < 2:
            return

        method = parts[0]

        proxy = pool.get_random()
        if not proxy:
            log.warning('Nincs elérhető proxy!')
            client_sock.sendall(b'HTTP/1.1 503 No Proxy Available\r\n\r\n')
            return

        proxy_host, proxy_port = proxy.rsplit(':', 1)

        log.info(f'{method} -> [{proxy}]')

        upstream = socket.create_connection((proxy_host, int(proxy_port)), timeout=PROXY_TIMEOUT)

        if method == 'CONNECT':
            upstream.sendall(data)
            resp = upstream.recv(BUFFER_SIZE)
            client_sock.sendall(resp)
            if b'200' in resp:
                forward_traffic(client_sock, upstream)
        else:
            upstream.sendall(data)
            forward_traffic(client_sock, upstream)

    except Exception as e:
        if proxy:
            pool.remove(proxy)
    finally:
        client_sock.close()
        if upstream:
            try:
                upstream.close()
            except:
                pass


def refresh_loop():
    while True:
        pool.refresh()
        time.sleep(REFRESH_INTERVAL)


def main():
    log.info('=== Rotating Proxy Server indul ===')
    log.info('Proxy lista betöltése...')

    refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
    refresh_thread.start()

    # Megvárjuk az első betöltést
    while pool.count() == 0:
        time.sleep(1)

    log.info(f'Proxy pool kész: {pool.count()} működő proxy')

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(200)

    log.info(f'')
    log.info(f'  Proxy fut: {LISTEN_HOST}:{LISTEN_PORT}')
    log.info(f'  Böngészőben állítsd be: HTTP Proxy = 127.0.0.1:{LISTEN_PORT}')
    log.info(f'  Minden kérésnél új IP-t használ')
    log.info(f'')

    while True:
        try:
            client, _ = server.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
        except KeyboardInterrupt:
            log.info('Leállítás...')
            break


if __name__ == '__main__':
    main()
