#!/usr/bin/env python3
import frida, sys, time, subprocess

HOOK_JS = r"""
Java.perform(function() {
    console.log('[*] Frida hook loaded');
    
    try {
        var Location = Java.use('android.location.Location');
        Location.isMock.implementation = function() {
            console.log('[+] isMock() -> false');
            return false;
        };
        Location.getMock.implementation = function() { return false; };
        Location.isFromMockProvider.implementation = function() {
            console.log('[+] isFromMockProvider() -> false');
            return false;
        };
        console.log('[OK] Location mock hooks installed!');
    } catch(e) { console.log('[!] Location hook: ' + e); }
    
    try {
        var LM = Java.use('android.location.LocationManager');
        LM.removeMockProvider.implementation = function(provider) {
            console.log('[+] BLOCKED removeMockProvider(' + provider + ')');
        };
        LM.removeMockProviderOverride.implementation = function(provider) {
            console.log('[+] BLOCKED removeMockProviderOverride(' + provider + ')');
        };
        console.log('[OK] LocationManager hooks installed!');
    } catch(e) { console.log('[!] LM hook: ' + e); }
});
"""

def on_msg(msg, data):
    t = msg.get("type", "?")
    d = msg.get("description", str(msg))
    print(f"  [{t}] {d}", flush=True)

print("Killing lptiyu...", flush=True)
subprocess.run([
    r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe",
    "-s", "10AD3P0298003QF", "shell", "am", "force-stop", "com.lptiyu.tanke"
], capture_output=True)
time.sleep(1)

device = frida.get_usb_device(timeout=5)
print(f"Device: {device.name}", flush=True)

print("Spawning lptiyu with Frida...", flush=True)
try:
    pid = device.spawn(["com.lptiyu.tanke"])
    print(f"  Spawned PID: {pid}", flush=True)
    
    session = device.attach(pid)
    script = session.create_script(HOOK_JS)
    script.on("message", on_msg)
    script.load()
    print("  Hook script loaded!", flush=True)
    
    device.resume(pid)
    print("  Resumed! App running with hooks.\n", flush=True)
    print("=" * 60, flush=True)
    print("  Frida hook is ACTIVE!", flush=True)
    print("  Now run your GPS injection script.", flush=True)
    print("  Press Ctrl+C to detach.", flush=True)
    print("=" * 60, flush=True)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDetaching...", flush=True)
        session.detach()
        print("Done.", flush=True)
        
except Exception as e:
    print(f"\n[X] {type(e).__name__}: {e}", flush=True)
    print("\nTrying with frida command line...", flush=True)
    import os
    os.system('frida -U -f com.lptiyu.tanke -l "' + __file__ + '"')