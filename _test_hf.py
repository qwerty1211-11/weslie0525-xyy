#!/usr/bin/env python3
import subprocess, time, math, random, re, sys, threading

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEVICE = "10AD3P0298003QF"
LAT, LNG = 41.6872, 123.6306

def adb(*args, timeout=10):
    cmd = [ADB, "-s", DEVICE] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except:
        return "", "", -1

def cmd_loc(*args):
    return adb("shell", "cmd", "location", "providers", *args, timeout=2)

R_EARTH = 6371000.0
def offset(lat, lng, dy, dx):
    dlat = dy / R_EARTH * 180.0 / math.pi
    dlng = dx / (R_EARTH * math.cos(math.radians(lat))) * 180.0 / math.pi
    return lat + dlat, lng + dlng

def setup():
    print("[1] Cleanup...")
    for p in ["gps", "network", "fused"]:
        cmd_loc("set-test-provider-enabled", p, "false")
        cmd_loc("remove-test-provider", p)
    
    print("[2] Permissions...")
    adb("shell", "appops", "set", "2000", "MOCK_LOCATION", "allow")
    adb("shell", "appops", "set", "shell", "MOCK_LOCATION", "allow")
    adb("shell", "settings", "delete", "secure", "mock_location_app")
    
    print("[3] GPS test provider...")
    cmd_loc("add-test-provider", "gps", "--supportsAltitude", "--supportsSpeed",
            "--supportsBearing", "--requiresSatellite")
    cmd_loc("set-test-provider-enabled", "gps", "true")
    cmd_loc("add-test-provider", "network")
    cmd_loc("set-test-provider-enabled", "network", "true")
    cmd_loc("add-test-provider", "fused", "--supportsAltitude", "--supportsSpeed", "--supportsBearing")
    cmd_loc("set-test-provider-enabled", "fused", "true")
    
    print("[4] Launch lptiyu...")
    adb("shell", "am", "force-stop", "com.lptiyu.tanke")
    time.sleep(0.5)
    adb("shell", "am", "start", "-n", "com.lptiyu.tanke/.activities.splash.SplashActivity")
    time.sleep(5)
    
    out, _, _ = adb("shell", "pidof", "com.lptiyu.tanke")
    print(f"    PID: {out}")

def get_counter():
    out, _, _ = adb("shell", "dumpsys", "location", timeout=8)
    mx = 0
    for l in out.splitlines():
        if "lptiyu" in l.lower() and "locations = " in l:
            m = re.search(r'locations = (\d+)', l)
            if m:
                mx = max(mx, int(m.group(1)))
    return mx

def check_running():
    out, _, _ = adb("shell", "dumpsys", "location", timeout=8)
    for l in out.splitlines():
        s = l.strip()
        if "lptiyu" not in s.lower() or "ProviderRequest[" not in s or "@+" not in s:
            continue
        if re.match(r'^\d{2}-\d{2} ', s):
            continue
        if "PASSIVE" in s or "OFF" in s:
            continue
        m = re.search(r'@\+([\dms]+)', s)
        if not m:
            continue
        s2 = m.group(1)
        ms = 0
        if 'ms' in s2:
            mm = re.search(r'(\d+)ms', s2)
            if mm: ms += int(mm.group(1))
        else:
            ss = re.search(r'(\d+)s', s2)
            if ss: ms += int(ss.group(1)) * 1000
            mm = re.search(r'(\d+)m(?!s)', s2)
            if mm: ms += int(mm.group(1)) * 60000
        if 0 < ms < 30000:
            return True, ms
    return False, 0

def high_freq_injector(stop_evt):
    """超高频注入线程 - 每 100ms 注入 3 个 provider"""
    lat, lng = LAT, LNG
    start = time.time()
    
    while not stop_evt.is_set():
        elapsed = time.time() - start
        speed_ms = 10 * 1000 / 3600
        
        ang = speed_ms / 300.0
        angle = ang * elapsed + math.radians(90)
        dx = math.cos(angle) * speed_ms / 10
        dy = math.sin(angle) * speed_ms / 10
        lat, lng = offset(lat, lng, dy, dx)
        lat += random.gauss(0, 0.5/1e7)
        lng += random.gauss(0, 0.5/1e7)
        
        ts = str(int(time.time() * 1000))
        
        # 注入所有 3 个 provider (gps + network + fused)
        for prov, acc in [("gps", random.uniform(3, 6)),
                          ("network", random.uniform(15, 30)),
                          ("fused", random.uniform(2, 5))]:
            cmd_loc("set-test-provider-location", prov,
                    "--location", f"{lat:.7f},{lng:.7f}",
                    "--accuracy", f"{acc:.1f}", "--time", ts)
        
        # 重新 enable 所有 provider (对抗乐跑的 disable)
        for prov in ["gps", "network", "fused"]:
            cmd_loc("set-test-provider-enabled", prov, "true")
        
        time.sleep(0.1)  # 100ms = 10Hz

def main():
    print("=" * 60)
    print("  V6 Super-High Frequency GPS Injection")
    print("  10Hz x 3 providers = 30 injections/sec")
    print("=" * 60)
    
    setup()
    
    prev = get_counter()
    print(f"\nInitial lptiyu counter: {prev}")
    print("Start RUNNING on phone! Injector starting...\n")
    
    stop_evt = threading.Event()
    inj = threading.Thread(target=high_freq_injector, args=(stop_evt,), daemon=True)
    inj.start()
    
    start = time.time()
    last_report = 0
    
    try:
        while True:
            time.sleep(3)
            
            is_run, interval = check_running()
            cnt = get_counter()
            delta = cnt - prev
            elapsed = int(time.time() - start)
            
            if is_run:
                status = f"RUN(i={interval}ms)"
            else:
                status = "WAIT..."
            
            print(f"[{elapsed}s] {status} | locs={cnt}(+{delta}) | ", end="", flush=True)
            
            if delta > 0:
                print(f"\n  >>> YES! lptiyu got {delta} new locations! <<<")
            
            prev = cnt
            
    except KeyboardInterrupt:
        stop_evt.set()
        print("\nStopping...")
        for p in ["gps", "network", "fused"]:
            cmd_loc("set-test-provider-enabled", p, "false")
            cmd_loc("remove-test-provider", p)

if __name__ == "__main__":
    main()