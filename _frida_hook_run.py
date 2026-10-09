#!/usr/bin/env python3
import frida, sys, time, threading

HOOK_JS = r"""
Java.perform(function() {
    console.log('[*] Frida hook loaded');
    
    try {
        var Location = Java.use('android.location.Location');
        Location.isMock.implementation = function() {
            console.log('[+] Location.isMock() -> false');
            return false;
        };
        Location.getMock.implementation = function() {
            console.log('[+] Location.getMock() -> false');
            return false;
        };
        Location.isFromMockProvider.implementation = function() {
            console.log('[+] Location.isFromMockProvider() -> false');
            return false;
        };
        console.log('[OK] Location mock hooks installed!');
    } catch(e) {
        console.log('[!] Location hook failed: ' + e);
    }
    
    try {
        var LM = Java.use('android.location.LocationManager');
        LM.removeMockProvider.implementation = function(provider) {
            console.log('[+] BLOCKED removeMockProvider(' + provider + ')');
        };
        LM.removeMockProviderOverride.implementation = function(provider) {
            console.log('[+] BLOCKED removeMockProviderOverride(' + provider + ')');
        };
        console.log('[OK] LocationManager hooks installed!');
    } catch(e) {
        console.log('[!] LocationManager hook failed: ' + e);
    }
    
    try {
        var SLM = Java.use('android.location.SettingsInjector');
        SLM.removeMockProvider.implementation = function(provider) {
            console.log('[+] BLOCKED SettingsInjector.removeMockProvider(' + provider + ')');
        };
    } catch(e) {}
    
    setTimeout(function() {
        Java.enumerateLoadedClasses({
            onMatch: function(name) {
                if (name.indexOf('lptiyu') >= 0 || name.indexOf('tanke') >= 0) {
                    console.log('[APP] ' + name);
                }
            },
            onComplete: function() {}
        });
    }, 3000);
});
"""

def on_message(msg, data):
    t = msg.get("type", "?")
    desc = msg.get("description", str(msg))
    if t == "send":
        print(f"  [send] {desc}")
    elif t == "error":
        print(f"  [err]  {desc}")
    else:
        print(f"  {desc}")

print("=" * 60)
print("  Frida Hook for 步道乐跑 - Bypass Mock Detection")
print("=" * 60)

device = frida.get_usb_device(timeout=5)
print(f"\nDevice: {device.name}")

print("\n[1] Force-stop lptiyu...")
import subprocess
subprocess.run(["adb", "shell", "am", "force-stop", "com.lptiyu.tanke"], capture_output=True)
time.sleep(0.5)

print("[2] Spawning lptiyu with Frida...")
try:
    pid = device.spawn(["com.lptiyu.tanke"])
    print(f"    Spawned PID: {pid}")
    
    session = device.attach(pid)
    print(f"    Attached OK")
    
    script = session.create_script(HOOK_JS)
    script.on("message", on_message)
    script.load()
    print("    Hook script loaded!")
    
    device.resume(pid)
    print("    Resumed! App is running with hooks.\n")
    
    print("=" * 60)
    print("  Frida hook active! Now run GPS injection script.")
    print("  Press Ctrl+C to exit.")
    print("=" * 60)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDetaching...")
        session.detach()
        
except frida.PermissionDeniedError as e:
    print(f"\n[X] PermissionDeniedError: {e}")
    print("    frida-server running as shell(2000) cannot attach to app")
    print("    Try: adb root + run frida-server as root")
    
except Exception as e:
    print(f"\n[X] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()