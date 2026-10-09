#!/usr/bin/env python3
import subprocess, time, math, random, re, sys

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEVICE = "10AD3P0298003QF"
LAT, LNG = 41.68726, 123.6306

def adb(*args, timeout=10):
    cmd = [ADB, "-s", DEVICE] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), -1

def setup():
    print("\n[Setup] Cleaning...")
    for p in ["gps", "network", "fused"]:
        adb("shell", "cmd", "location", "providers", "set-test-provider-enabled", p, "false")
        adb("shell", "cmd", "location", "providers", "remove-test-provider", p)
    
    adb("shell", "am", "force-stop", "com.lptiyu.tanke")
    time.sleep(1)
    
    adb("shell", "appops", "set", "2000", "MOCK_LOCATION", "allow")
    adb("shell", "appops", "set", "shell", "MOCK_LOCATION", "allow")
    adb("shell", "settings", "delete", "secure", "mock_location_app")
    
    print("[Setup] Adding test providers...")
    adb("shell", "cmd", "location", "providers", "add-test-provider", "gps",
        "--supportsAltitude", "--supportsSpeed", "--supportsBearing", "--requiresSatellite")
    adb("shell", "cmd", "location", "providers", "set-test-provider-enabled", "gps", "true")
    adb("shell", "cmd", "location", "providers", "add-test-provider", "network")
    adb("shell", "cmd", "location", "providers", "set-test-provider-enabled", "network", "true")
    adb("shell", "cmd", "location", "providers", "add-test-provider", "fused",
        "--supportsAltitude", "--supportsSpeed", "--supportsBearing")
    adb("shell", "cmd", "location", "providers", "set-test-provider-enabled", "fused", "true")
    
    print("[Setup] Launching lptiyu...")
    adb("shell", "am", "start", "-n", "com.lptiyu.tanke/.activities.splash.SplashActivity")
    time.sleep(4)
    
    out, _, _ = adb("shell", "pidof", "com.lptiyu.tanke")
    print(f"[Setup] lptiyu PID: {out}")

def inject(lat, lng):
    ts = str(int(time.time() * 1000))
    for prov, acc in [("gps", f"{random.uniform(3, 6):.1f}"),
                      ("network", f"{random.uniform(15, 30):.1f}"),
                      ("fused", f"{random.uniform(2, 5):.1f}")]:
        adb("shell", "cmd", "location", "providers",
            "set-test-provider-location", prov,
            "--location", f"{lat:.7f},{lng:.7f}",
            "--accuracy", acc, "--time", ts)
        adb("shell", "cmd", "location", "providers",
            "set-test-provider-enabled", prov, "true")

def get_lptiyu_counter():
    out, _, _ = adb("shell", "dumpsys", "location", timeout=8)
    mx = 0
    for line in out.splitlines():
        low = line.lower()
        if "lptiyu" in low and "locations = " in low:
            m = re.search(r'locations = (\d+)', line)
            if m:
                mx = max(mx, int(m.group(1)))
    return mx

def check_lptiyu_running():
    out, _, _ = adb("shell", "dumpsys", "location", timeout=8)
    for line in out.splitlines():
        s = line.strip()
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
        total_ms = 0
        if 'ms' in s2:
            mm = re.search(r'(\d+)ms', s2)
            if mm:
                total_ms += int(mm.group(1))
        else:
            ss = re.search(r'(\d+)s', s2)
            if ss:
                total_ms += int(ss.group(1)) * 1000
            mm = re.search(r'(\d+)m(?!s)', s2)
            if mm:
                total_ms += int(mm.group(1)) * 60000
        if 0 < total_ms < 30000:
            return True, total_ms
    return False, 0

def main():
    print("=" * 60)
    print("  Budaole GPS Injection V7")
    print("=" * 60)
    
    setup()
    
    R_EARTH = 6371000.0
    lat, lng = LAT, LNG
    
    counter_prev = get_lptiyu_counter()
    print(f"\n[Monitor] Initial lptiyu locations: {counter_prev}")
    print("[Monitor] >>> Please tap 'Start Running' on your phone! <<<")
    print()
    
    start = time.time()
    
    try:
        while True:
            elapsed = time.time() - start
            
            # Humanized speed curve: warmup 0 -> 2.5m/s -> steady -> fatigue
            if elapsed < 30:
                speed = 2.5 * (elapsed / 30)
            elif elapsed < 600:
                speed = 2.5 + random.uniform(-0.3, 0.3)
            else:
                speed = max(1.8, 2.5 - (elapsed - 600) / 3600) + random.uniform(-0.2, 0.2)
            
            # Walk pattern: forward with slight wobble
            angle = math.radians(90) + math.sin(elapsed * 0.5) * 0.3
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            
            dlat = (dy / R_EARTH) * (180.0 / math.pi)
            dlng = (dx / (R_EARTH * math.cos(math.radians(lat)))) * (180.0 / math.pi)
            lat += dlat
            lng += dlng
            
            lat += random.gauss(0, 0.3 / 1e7)
            lng += random.gauss(0, 0.3 / 1e7)
            
            # Inject!
            inject(lat, lng)
            
            # Report every 3 seconds
            if int(elapsed) % 3 == 0 and int(elapsed) != int(elapsed - 0.2):
                is_run, interval = check_lptiyu_running()
                counter = get_lptiyu_counter()
                delta = counter - counter_prev
                
                status = f"RUN(i={interval}ms)" if is_run else "WAIT..."
                print(f"[{int(elapsed)}s] {status} | lptiyu_locs={counter}(+{delta}) | gps=({lat:.5f},{lng:.5f})", flush=True)
                
                if delta > 0:
                    print(f"  >>> YES! lptiyu got {delta} new locations! <<<", flush=True)
                
                counter_prev = counter
            
            time.sleep(0.1)  # 10Hz injection
            
    except KeyboardInterrupt:
        print("\n[Stop] Cleaning up...")
        for p in ["gps", "network", "fused"]:
            adb("shell", "cmd", "location", "providers", "set-test-provider-enabled", p, "false")
            adb("shell", "cmd", "location", "providers", "remove-test-provider", p)
        print("[Stop] Done")

if __name__ == "__main__":
    main()