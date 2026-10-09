#!/usr/bin/env python3
import frida, sys, time

HOOK_JS = r"""
Java.perform(function() {
    console.log('[*] Frida hook loaded');
    
    try {
        var Location = Java.use('android.location.Location');
        Location.isMock.implementation = function() { return false; };
        Location.getMock.implementation = function() { return false; };
        Location.isFromMockProvider.implementation = function() { return false; };
        console.log('[OK] Location.isMock() -> false hooked!');
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
    print(f"  [{t}] {d}")

pid = int(sys.argv[1]) if len(sys.argv) > 1 else None

device = frida.get_usb_device(timeout=5)
print(f"Device: {device.name}")

if pid:
    print(f"Attaching to PID {pid}...")
    session = device.attach(pid)
else:
    print("Spawning lptiyu...")
    pid = device.spawn(["com.lptiyu.tanke"])
    print(f"Spawned PID: {pid}")
    session = device.attach(pid)

print("Attached! Loading hook...")
script = session.create_script(HOOK_JS)
script.on("message", on_msg)
script.load()

if not sys.argv[1]:
    device.resume(pid)
    print("Resumed!")

print("\nHook active! Press Ctrl+C to detach.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    session.detach()
    print("\nDetached.")