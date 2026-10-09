import subprocess, time, re, math, random

ADB = r'C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe'
DEV = '10AD3P0298003QF'
def adb(*a, t=10):
    cmd=[ADB,'-s',DEV]+list(a)
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=t,encoding='utf-8',errors='replace')
        return r.stdout.strip(),r.stderr.strip(),r.returncode
    except: return '','',-1

LAT, LNG = 41.6872, 123.6306

print('[1] 清理所有 test provider...')
for p in ['gps','network','fused']:
    adb('shell','cmd','location','providers','set-test-provider-enabled',p,'false')
    adb('shell','cmd','location','providers','remove-test-provider',p)
adb('shell','settings','delete','secure','mock_location_app')
time.sleep(1)

print('[2] 设置 VIVO mock GPS location + 开启 mock...')
adb('shell','settings','put','secure','mock_location','1')
adb('shell','settings','put','secure','mock_gps_location',str(LAT)+','+str(LNG))
print('  mock_gps_location set')
time.sleep(2)

print('\n[3] 检查 location (是否带 mock 标记)...')
out,_,_ = adb('shell','dumpsys','location',t=8)
for l in out.splitlines():
    s = l.strip()
    if 'last location=' in s:
        has_mock = ('mock' in s.lower()) or ('M:' in s)
        tag = 'MOCK' if has_mock else 'REAL '
        print('  ['+tag+'] '+s[:150])
        break

print('\n[4] 检查乐跑跑步状态...')
running = False
for l in out.splitlines():
    s = l.strip()
    if 'lptiyu' in s.lower() and 'ProviderRequest[' in s and '@+' in s:
        if re.match(r'^\d{2}-\d{2}', s): continue
        if 'OFF' in s or 'PASSIVE' in s: continue
        print('  活跃请求: '+s[:120])
        running = True

if not running:
    print('  乐跑没跑步! 等 15s...')
    time.sleep(15)

print('\n[5] 15s 循环更新 VIVO mock GPS...')
def off(lat,lng,dy,dx):
    dlat = dy/6371000.0*180/math.pi
    dlng = dx/(6371000.0*math.cos(math.radians(lat)))*180/math.pi
    return lat+dlat, lng+dlng

def get_counter():
    o,_,_ = adb('shell','dumpsys','location',t=6)
    maxc = 0
    for l in o.splitlines():
        if 'lptiyu' in l.lower() and 'locations = ' in l:
            m = re.search(r'locations = (\d+)', l)
            if m: maxc = max(maxc, int(m.group(1)))
    return maxc

c0 = get_counter()
print('  初始 counter = '+str(c0))

lat, lng = LAT, LNG
speed_ms = 12 * 1000 / 3600

for i in range(15):
    lat, lng = off(lat, lng, speed_ms + random.uniform(-0.5,0.5), random.uniform(-0.5,0.5))
    adb('shell','settings','put','secure','mock_gps_location',
        '{:.7f},{:.7f}'.format(lat, lng))
    time.sleep(1)
    if i % 5 == 4:
        c = get_counter()
        print('  {}s: counter={} (+{}) loc=({:.5f},{:.5f})'.format(i+1,c,c-c0,lat,lng))

c1 = get_counter()

print('\n' + '='*60)
print('INIT={} FINAL={} DELTA={}'.format(c0,c1,c1-c0))
out2,_,_ = adb('shell','dumpsys','location',t=6)
for l in out2.splitlines():
    if 'last location=' in l:
        has_mock = ('mock' in l.lower()) or ('M:' in l)
        tag = 'MOCK' if has_mock else 'REAL '
        print('  location ['+tag+']: '+l.strip()[:130])
        break

if c1-c0 > 50:
    print('  >>> VIVO mock GPS works!! Check phone now!!')
elif c1-c0 > 0:
    print('  >>> Got {} locations but isMock filtered maybe'.format(c1-c0))
else:
    print('  >>> VIVO mock GPS also not working...')
print('='*60)