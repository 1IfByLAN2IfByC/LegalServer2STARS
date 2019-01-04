import tornado.ioloop
import tornado.web
import tornado.auth
from tornado import autoreload
from datetime import datetime
import motor
import json
import os
import pprint
import asyncio 
from lsclient import LSClient
import logging

pollinterval = 100 # time between LS polls (ms)

class MainHandler(tornado.web.RequestHandler):
    async def get(self):
        db = self.settings['db']

        await uploader.periodic_check()



class Uploader(object):
    def __init__(self, lsclient):
        self.lsclient = lsclient

    async def _check_new_LS(self):
        ''' connect to LS, check for new requests. will return
            true if new/updated records exist, false if none 
            
            returns
            -------
                newvalues: bool
        '''
    
        newvalues = await self.lsclient.check_new()
        return newvalues
    
    async def _upload_to_STARS(self):
        ''' take values from queue, translate them into STARS-complient 
            format, post to STARS, update LS ledger with confirmation code,
            and pop from queue
        '''

        pass

    async def periodic_check(self):
        newvalues = False
        while not newvalues:
            newvalues = await self._check_new_LS()
            asyncio.sleep(pollinterval)
        
        # new values detected and added to queue
        await self._upload_to_STARS()
        
def main():
    import tornado.web
    import tornado.autoreload
    from queuerunner import QueueRunner
    from lsdatabasedriver import LSDBDriver
    import motor 
    tornado.autoreload.start()
    default_path='configs/logconfig.json'
    default_level=logging.INFO

    client = motor.motor_tornado.MotorClient('localhost', 27017)
    db = client.TLSC
    col = db.LegalServer

    schema = 'configs/LSschema.json'
    dbdriver = LSDBDriver(db, schema)

    with open(default_path, 'r') as f:
        config = json.load(f)

    logging.config.dictConfig(config)
    log = logging.getLogger(__name__)

    with open("/users/mikelee/Desktop/test.txt", 'r') as f:
        auth = [r.rstrip() for r in f]
    
    queue = QueueRunner(db.Queue, log)

    with open("/users/mikelee/Desktop/test.txt", 'r') as f:
        auth = [r.rstrip() for r in f]
        
    lsclient = LSClient(auth[0], (auth[1], auth[2]), dbdriver, queue, log)

    print('startup')

    global uploader
    uploader = Uploader(lsclient)

    application = tornado.web.Application([
        (r'/', MainHandler)
        ], db=dbdriver)

    application.listen(5000)
    tornado.ioloop.IOLoop.current().start()

if __name__ == '__main__':
    main()