import httpx
import json
import time

class XUIManager:
    def __init__(self, url, user, password):
        # Отрезаем лишние слеши в конце, если они есть
        self.url = url.rstrip('/')
        self.user = user
        self.password = password
        self.cookies = None

    async def login(self):
        async with httpx.AsyncClient(verify=False) as client:
            # Путь к логину всегда приклеивается к базовому URL панели
            r = await client.post(f"{self.url}/login", data={
                "username": self.user, 
                "password": self.password
            })
            if r.status_code == 200:
                self.cookies = r.cookies
                return True
            return False

    async def add_client(self, inbound_id, email, client_uuid, months=1):
        if not self.cookies: 
            await self.login()
        
        expiry_time = int((time.time() + months * 30 * 24 * 3600) * 1000)
        
        # Для 3X-UI настройки клиента должны быть JSON-строкой внутри поля settings
        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": client_uuid,
                    "email": email,
                    "expiryTime": expiry_time,
                    "enable": True,
                    "limitIp": 2,
                    "totalGB": 0
                }]
            })
        }
        
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(
                f"{self.url}/panel/api/inbounds/addClient", 
                json=payload, 
                cookies=self.cookies
            )
            return r.status_code == 200

    async def delete_client(self, inbound_id, email):
        if not self.cookies: 
            await self.login()
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(
                f"{self.url}/panel/api/inbounds/delClient/{inbound_id}/{email}", 
                cookies=self.cookies
            )
            return r.status_code == 200
