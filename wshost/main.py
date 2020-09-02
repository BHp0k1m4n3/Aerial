import websockets
import json
import asyncio
import ssl
import logging as log
import lib
from yaml import safe_load
from mysql.connector import connect as dbconnect

log.basicConfig(
    filename="wshost.log",
    format="WSHost @ %(asctime)s | %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=log.INFO,
)

loop = asyncio.get_event_loop()
config = safe_load(open("config.yml", "r"))
db = dbconnect(
    host=config["Database"]["Host"],
    port=config["Database"]["Port"],
    user=config["Database"]["Username"],
    password=config["Database"]["Password"],
    database="aerial",
)

# Main WebSocket Handler
async def wshandle(ws, path):
    #if ws.remote_address[0] not in config["Allowed_IPs"]:
    if False:
        log.warning("Denied WebSocket Connection from " + ws.remote_address[0])
        await ws.close(code=4000, reason="Unauthorized")
        return
    log.info("Established WebSocket Connection")
    c = db.cursor()
    c.execute(
        """SELECT * FROM `accounts` WHERE `in_use` = '0' ORDER BY RAND() LIMIT 1;"""
    )
    details = c.fetchone()
    if details is None:
        await ws.close(code=4001, reason="No Free Accounts")
        return
    c.execute(
        """UPDATE `accounts` SET `in_use` = '1' WHERE `id` = '%s';""" % details[0]
    )
    db.commit()
    bot = lib.Client(
        {
            "device_id": details[3],
            "account_id": details[4],
            "secret": details[5],
        },
        ws,
    )
    log.info("Claimed Account " + str(details[0]))
    loop.create_task(bot.start())
    await bot.wait_until_ready()
    await ws.send(
        json.dumps(
            {
                "type": "account_info",
                "username": bot.user.display_name,
                "outfit": "CID_565_Athena_Commando_F_RockClimber",
            }
        )
    )
    async for message in ws:
        await lib.process(bot, json.loads(message))
    await bot.close()
    c.execute(
        """UPDATE `accounts` SET `in_use` = '0' WHERE `id` = '%s';""" % details[0]
    )
    db.commit()


async def start():
    await websockets.server.serve(
        wshandle,
        "188.166.36.137",
        8765,
        ssl=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(
            certfile="ssl/cert.pem", keyfile="ssl/key.pem"
        ),
    )


loop.create_task(start())
loop.run_forever()
