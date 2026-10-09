import subprocess, sys, time, math, re, random, threading

ADB = r'C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe'
DEV = '10AD3P0298003QF'
PKG = 'com.lptiyu.tanke'
LAT, LNG = 41.6872, 123.6306

def adb(*a, t=10):
    cmd=[ADB,'-s',DEV]+list(a)
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=t,encoding='utf-8',errors='replace')
        return r.stdout.strip(),r.stderr.strip(),r.returncode
    except: return '','',-1

def cloc(*a, t=5):
    return adb('shell','cmd','location','providers',*a,t=t)

FRIDA_JS = """
Java.perform(function() {
    console.log('[*] Frida Hook attached to ' + '%s');
    
    try {
        var Location = Java.use('android.location.Location');
        
        Location.isMock.implementation = function() {
            return false;
        };
        console.log('[+] Location.isMock() -> false');
        
        Location.getMock.implementation = function() {
            return false;
        };
        console.log('[+] Location.getMock() -> false');
        
        Location.isFromMockProvider.implementation = function() {
            return false;
        };
        console.log('[+] Location.isFromMockProvider() -> false');
        
        try {
            var LocationCompat = Java.use('androidx.core.location.LocationCompat');
            LocationCompat.isMock.implementation = function(loc) {
                return false;
            };
            console.log('[+] LocationCompat.isMock() -> false');
        } catch(e) {}
        
        try {
            var LocationUtils = Java.use('com.amap.api.services.core.LocationUtils');
            LocationUtils.isMock.implementation = function(loc) {
                return false;
            };
            console.log('[+] AMap LocationUtils.isMock() -> false');
        } catch(e) {}
        
        try {
            var LocationManager = Java.use('android.location.LocationManager');
            var hasMock = LocationManager.hasMockLocationProviders;
            if (hasMock !== undefined) {
                hasMock.implementation = function() { return false; };
                console.log('[+] LocationManager.hasMockLocationProviders() -> false');
            }
        } catch(e) {}
        
        console.log('[*] All hooks installed!');
    } catch(e) {
        console.log('[-] Hook failed: ' + e);
    }
});
""" % PKG

def setup_gps():
    print('[GPS] Setting up test providers...')
    adb('shell','appops','set','2000','MOCK_LOCATION','allow')
    adb('shell','appops','set','shell','MOCK_LOCATION','allow')
    for p in ['gps','network','fused']:
        cloc('set-test-provider-enabled',p,'false')
        cloc('remove-test-provider',p)
    cloc('add-test-provider','gps','--supportsAltitude','--supportsSpeed','--supportsBearing','--requiresSatellite')
    cloc('set-test-provider-enabled','gps','true')
    cloc('add-test-provider','network','--requiresNetwork')
    cloc('set-test-provider-enabled','network','true')
    cloc('add-test-provider','fused','--supportsAltitude','--supportsSpeed','--supportsBearing')
    cloc('set-test-provider-enabled','fused','true')
    print('[GPS] Ready!')

def inject(lat, lng, acc=4.0):
    t = str(int(time.time()*1000))
    for p in ['gps','network','fused']:
        cloc('set-test-provider-location',p,
             '--location','{:.7f},{:.7f}'.format(lat,lng),
             '--accuracy',str(acc),'--time',t)

def gps_loop(stop_evt):
    lat, lng = LAT, LNG
    speed_ms = 12 * 1000 / 3600
    R = 6371000.0
    def off(la,ln,dy,dx):
        dlat = dy/R*180/math.pi
        dlng = dx/(R*math.cos(math.radians(la)))*180/math.pi
        return la+dlat, ln+dlng
    
    print('[GPS] Starting injection loop 4x/s...')
    while not stop_evt.is_set():
        lat, lng = off(lat, lng, speed_ms/4+random.uniform(-0.3,0.3), random.uniform(-0.3,0.3))
        inject(lat, lng, acc=random.uniform(3,8))
        time.sleep(0.25)

def get_counter():
    o,_,_ = adb('shell','dumpsys','location',t=6)
    maxc = 0
    for l in o.splitlines():
        if 'lptiyu' in l.lower() and 'locations = ' in l:
            m = re.search(r'locations = (\d+)', l)
            if m: maxc = max(maxc, int(m.group(1)))
    return maxc

def lepao_running():
    o,_,_ = adb('shell','dumpsys','location',t=6)
    for l in o.splitlines():
        s = l.strip()
        if 'lptiyu' in s.lower() and 'ProviderRequest[' in s and '@+' in s:
            if re.match(r'^\d{2}-\d{2}', s): continue
            if 'OFF' in s or 'PASSIVE' in s: continue
            return True
    return False

def find_pid():
    o,_,_ = adb('shell','pidof',PKG)
    pids = o.split()
    return pids[0] if pids else None

print('='*60)
print('  Frida Hook + GPS Injection for Budaole')
print('='*60)

print('\n[1] Make sure frida-server is running...')
o,_,_ = adb('shell','ps','-A')
if 'frida-server' in o:
    print('  frida-server is running!')
else:
    print('  ERROR: frida-server not running!')
    sys.exit(1)

print('\n[2] Setup test providers (GPS injection)...')
setup_gps()

print('\n[3] Check if Budaole is running...')
pid = find_pid()
if pid:
    print('  Budaole PID = '+pid)
else:
    print('  Starting Budaole...')
    adb('shell','am','force-stop',PKG)
    time.sleep(0.5)
    adb('shell','am','start','-n',PKG+'/.activities.splash.SplashActivity')
    time.sleep(6)
    for _ in range(15):
        pid = find_pid()
        if pid: break
        time.sleep(2)

if not pid:
    print('  ERROR: Budaole not starting!')
    sys.exit(1)

print('  Budaole PID = '+pid)

print('\n[4] Check Budaole running mode...')
if not lepao_running():
    print('  Budaole is NOT in running mode!')
    print('  PLEASE go to phone and tap START RUNNING!')
    for _ in range(45):
        time.sleep(2)
        if lepao_running():
            print('  Budaole started running!')
            break
    else:
        print('  Budaole still not running after 90s...')
        sys.exit(1)

print('  Budaole is actively requesting GPS!')

print('\n[5] Start GPS injection thread...')
stop_evt = threading.Event()
gps_thread = threading.Thread(target=gps_loop, args=(stop_evt,), daemon=True)
gps_thread.start()

print('\n[6] Frida attach and hook...')
import frida
device = frida.get_usb_device(timeout=10)
print('  Frida device = '+str(device))

pid_int = int(pid)
session = device.attach(pid_int)
script = session.create_script(FRIDA_JS)

def on_message(msg, data):
    if msg['type'] == 'send':
        print('  [Frida] '+str(msg['payload']))
    else:
        print('  [Frida] '+str(msg.get('description', msg)))

script.on('message', on_message)
script.load()

print('\n[7] Monitoring (60s)...')
c0 = get_counter()
print('  Initial counter = '+str(c0))

try:
    for i in range(60):
        time.sleep(1)
        if i % 10 == 9:
            c = get_counter()
            alive = lepao_running()
            print('  {}s: counter={} (+{}) alive={}'.format(
                i+1, c, c-c0, alive))
except KeyboardInterrupt:
    pass

c1 = get_counter()
stop_evt.set()
session.detach()

print('\n' + '='*60)
print('RESULT: INIT={} FINAL={} DELTA={}'.format(c0, c1, c1-c0))

o2,_,_ = adb('shell','dumpsys','location',t=6)
for l in o2.splitlines():
    if 'last location=' in l:
        has_mock = ('mock' in l.lower()) or ('M:' in l)
        tag = 'MOCK' if has_mock else 'REAL '
        print('  Current location ['+tag+']: '+l.strip()[:130])
        break

if c1-c0 > 50:
    print('  >>> SUCCESS!! Check your phone now!!')
    print('  >>> MILEAGE SHOULD BE INCREASING!!')
elif c1-c0 > 0:
    print('  >>> Got locations but hook may not have worked')
else:
    print('  >>> No counter growth - hook may have failed')
print('='*60)