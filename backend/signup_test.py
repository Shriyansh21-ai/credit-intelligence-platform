import json
import urllib.request
import urllib.error

url = 'http://127.0.0.1:8000/signup'
data = json.dumps({'email': 'test@example.com', 'password': 'Test1234'}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print('status', resp.status)
        print(resp.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print('status', e.code)
    print(e.read().decode('utf-8', errors='replace'))
except Exception as e:
    import traceback
    traceback.print_exc()
