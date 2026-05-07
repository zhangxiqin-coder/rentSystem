import json, urllib.request, random
base='http://127.0.0.1:8000/api/v1'
user='u'+str(random.randint(10000,99999))
pwd='Aa123456'
email=f'{user}@example.com'
results=[]

def post(path,data):
    b=json.dumps(data).encode()
    req=urllib.request.Request(base+path,data=b,method='POST',headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req,timeout=10).read().decode())

def get(path,token=None):
    h={}
    if token: h['Authorization']='Bearer '+token
    req=urllib.request.Request(base+path,headers=h,method='GET')
    return json.loads(urllib.request.urlopen(req,timeout=10).read().decode())

try:
    post('/auth/register',{'username':user,'email':email,'password':pwd}); results.append('REGISTER_OK')
except Exception as e:
    results.append('REGISTER_FAIL:'+str(e))
try:
    login=post('/auth/login',{'username':user,'password':pwd}); token=login.get('data',{}).get('access_token'); results.append('LOGIN_OK' if token else 'LOGIN_NO_TOKEN')
except Exception as e:
    token=None; results.append('LOGIN_FAIL:'+str(e))
try:
    me=get('/auth/me',token); results.append('ME_OK' if me.get('data',{}).get('user',{}).get('username')==user else 'ME_FAIL')
except Exception as e:
    results.append('ME_ERR:'+str(e))
open('D:/codespace/rentSystem/backend/test_results.json','w',encoding='utf-8').write(json.dumps({'user':user,'results':results},ensure_ascii=False))
