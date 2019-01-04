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

pollinterval = 100 # time between LS polls (ms)

class MainHandler(tornado.web.RequestHandler):
    async def get(self):
        db = self.settings['db']

        await lsserver.startup()

    async def periodic_check(self):
        newvalues = False
        while not newvalues:
            uploader.

        

class Uploader(object):
    def __init__(self, lsclient, queue):
        self.lsclient = lsclient
        self.queue = queue

    async def startup(self):
        await lsclient.startup()

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
    client = motor.motor_tornado.MotorClient('localhost', 27017)
    db = client.TLSC

    schema = 'configs/LSschema.json'
    dbdriver = LSDBDriver(db, schema)

    with open(default_path, 'r') as f:
        config = json.load(f)

    logging.config.dictConfig(config)
    log = logging.getLogger(__name__)

    with open("/users/mikelee/Desktop/test.txt", 'r') as f:
        auth = [r.rstrip() for r in f]
        
    lsserver = LSClient(auth[0], (auth[1], auth[2]), dbdriver, log)

    print('startup')


    application = tornado.web.Application([
        (r'/', MainHandler)
        ], db=dbdriver)

    application.listen(5000)
    tornado.ioloop.IOLoop.current().start()

if __name__ == '__main__':
    main()