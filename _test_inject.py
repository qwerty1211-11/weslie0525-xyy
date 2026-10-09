#!/usr/bin/env python3
import subprocess, time, math, random, re, sys

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEVICE = "10AD3P0298003QF"
LAT, LNG = 41.6872, 123.6306

def adb(*args, timeout=10):
    cmd = [ADB, "-s", DEVICE] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), -1

def sh(c):
    return adb("shell", "sh", "-c", c)

def cmd_loc(*args):
    return adb("shell", "cmd", "location", "providers", *args)

R_EARTH = 6371000.0
def offset(lat, lng, dy, dx):
    dlat = dy / R_EARTH * 180.0 / math.pi
    dlng = dx / (R_EARTH * math.cos(math.radians(lat))) * 180.0 / math.pi
    return lat + dlat, lng + dlng

def setup():
    print("[1] Cleaning old providers...")
    for p in ["gps", "network", "fused"]:
        cmd_loc("set-test-provider-enabled", p, "false")
        cmd_loc("remove-test-provider", p)
    
    print("[2] Granting MOCK_LOCATION...")
    adb("shell", "appops", "set", "2000", "MOCK_LOCATION", "allow")
    adb("shell", "appops", "set", "shell", "MOCK_LOCATION", "allow")
    adb("shell", "settings", "delete", "secure", "mock_location_app")
    
    print("[3] Adding GPS test provider...")
    cmd_loc("add-test-provider", "gps", "--supportsAltitude", "--supportsSpeed",
            "--supportsBearing", "--requiresSatellite")
    cmd_loc("set-test-provider-enabled", "gps", "true")
    
    print("[4] Injecting initial GPS...")
    ts = str(int(time.time() * 1000))
    cmd_loc("set-test-provider-location", "gps",
            "--location", f"{LAT:.7f},{LNG:.7f}",
            "--accuracy", "5.0", "--time", ts)
    time.sleep(0.5)
    
    out, _, _ = adb("shell", "dumpsys", "location")
    mock_count = out.lower().count("mock")
    print(f"    System has {mock_count} 'mock' references")
    print("    GPS test provider ready!")

def get_lptiyu_counter():
    out, _, _ = adb("shell", "dumpsys", "location", timeout=8)
    max_cnt = 0
    for l in out.splitlines():
        if "lptiyu" in l.lower() and "locations = " in l:
            m = re.search(r'locations = (\d+)', l)
            if m:
                max_cnt = max(max_cnt, int(m.group(1)))
    return max_cnt

def get_mock_status():
    out, _, _ = adb("shell", "dumpsys", "location", timeout=8)
    results = []
    for l in out.splitlines():
        if "gps provider" in l.lower() and "mock" in l.lower():
            results.append(l.strip())
        if "last location=" in l and "gps" in l.lower():
            results.append(l.strip())
    return results

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
        interval_str = m.group(1)
        total_ms = 0
        if 'ms' in interval_str:
            mm = re.search(r'(\d+)ms', interval_str)
            if mm:
                total_ms += int(mm.group(1))
        else:
            ss = re.search(r'(\d+)s', interval_str)
            if ss:
                total_ms += int(ss.group(1)) * 1000
            mmin = re.search(r'(\d+)m(?!s)', interval_str)
            if mmin:
                total_ms += int(mmin.group(1)) * 60000
        if 0 < total_ms < 30000:
            return True, total_ms
    return False, 0

def main():
    print("=" * 60)
    print("  GPS Injection Test - Budaole Anti-Debug")
    print("=" * 60)
    
    setup()
    
    print("\n[5] Launching Budaole...")
    adb("shell", "am", "force-stop", "com.lptiyu.tanke")
    time.sleep(0.5)
    adb("shell", "am", "start", "-n", "com.lptiyu.tanke/.activities.splash.SplashActivity")
    print("    App launched! Please tap 'Start Running' on phone.")
    time.sleep(5)
    
    prev_counter = get_lptiyu_counter()
    print(f"\n[6] Start injecting! Initial lptiyu counter = {prev_counter}")
    
    lat, lng = LAT, LNG
    speed_ms = 10 * 1000 / 3600
    start_time = time.time()
    last_report = 0
    last_counter_check = 0
    
    try:
        while True:
            elapsed = time.time() - start_time
            
            # Inject GPS
            ang = speed_ms / 300.0
            angle = ang * elapsed + math.radians(90)
            dx = math.cos(angle) * speed_ms / 4
            dy = math.sin(angle) * speed_ms / 4
            lat, lng = offset(lat, lng, dy, dx)
            lat += random.gauss(0, 1.0/1e7)
            lng += random.gauss(0, 1.0/1e7)
            
            ts = str(int(time.time() * 1000))
            cmd_loc("set-test-provider-location", "gps",
                    "--location", f"{lat:.7f},{lng:.7f}",
                    "--accuracy", f"{random.uniform(3, 8):.1f}", "--time", ts)
            
            # Check running status every 3s
            if elapsed - last_counter_check > 3:
                is_run, interval = check_running()
                cnt = get_lptiyu_counter()
                delta = cnt - prev_counter
                
                if is_run:
                    status = f"RUNNING (interval={interval}ms)"
                else:
                    status = f"WAITING..."
                
                print(f"\r  [{int(elapsed)}s] {status} | lptiyu_locations: {cnt} (+{delta}) | gps=({lat:.5f},{lng:.5f})   ", end="", flush=True)
                
                if delta > 0:
                    print(f"\n  >>> GREAT! lptiyu received {delta} new locations!")
                elif is_run and delta == 0 and elapsed > 15:
                    print(f"\n  >>> WARNING: lptiyu is running but not receiving locations!")
                    mock = get_mock_status()
                    for m in mock[:3]:
                        print(f"      {m}")
                
                prev_counter = cnt
                last_counter_check = elapsed
            
            time.sleep(0.25)
            
    except KeyboardInterrupt:
        print("\n\n[Stop] Cleaning up...")
        for p in ["gps", "network", "fused"]:
            cmd_loc("set-test-provider-enabled", p, "false")
            cmd_loc("remove-test-provider", p)
        print("Done.")

if __name__ == "__main__":
    main()