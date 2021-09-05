# PASTA
Ping And SMS Timeless Application 

функция отправки смс
функция проверки доступности оборудования (по ip-адресу)
http-сервер:
- /hosts/ (GET)
+ /hosts/<ip> (GET,PUT,DELETE) 
- /phones/ (GET)
- /phones/<phone> (GET,PUT,DELETE)
+ /send/<phone>/<message> (GET) 
- /start (GET)
- /stop (GET)
