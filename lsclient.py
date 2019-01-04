import requests as rq
import json
import xmltodict as xml
import logging
from hashlib import sha224
import asyncio 

from lsdatabasedriver import LSDBDriver

class LSClient(object):
    def __init__(self, apikey, auth, db, queue, log):

        '''
        inputs:
        -------
            apikey: str
                url corresponding to the report XML API
            
            auth: tuple of strings
                (username, password) for http authentication
                
            db: LSDBDriver
                database to store LS logs

            queue: QueueRunner
                collection to store records to be uploaded to STARS
            
            log: logging log
                log to store runs and id updates
            
        parameters:
        -----------
            reportids: dict
                all the report IDs that have already been uploaded
                {id: str(hash)}
                
            toupload: list of dicts
                row object returned by requests that are not in reportids
                (i.e. the need to be uploaded)      
        '''
        
        self.apikey = apikey
        self.auth = auth
        self._db = db
        self.log = log
        self._queue = queue
    
        self.toupload = []
        self.newrecords = []

    async def _id_check(self):
        ''' open the file where the permstore is and check if it is empty.
            run once on startup to minimize queries to the database'''
        
        self.reportids = await self._db.fetch_all()
        print('report ids', self.reportids)
 
    def _hash_wrapper(self, string):
        '''wrapper to save the single step of .encode(utf-8)'''
        return sha224(bytes(string.encode("utf-8"))).hexdigest()
   
    async def _pull_report(self):
        '''
        pull the report using requesets. authentication handled using http auth
        '''

        try:
            # if first time running, load ids from DB
            self.reportids
        except AttributeError:
            await self._id_check()

        self.log.debug('Attempting to make request')
        datareturn = rq.get(self.apikey, auth=(self.auth[0], self.auth[1]))

        # check datareturn error codes
        if datareturn.status_code != 200:
            print(datareturn.status_code)
            self.log.debug('Bad request. Error code: {}'.format(datareturn.status_code))
            print(datareturn)
            # raise some error
            raise ValueError
            
        else:
            newrecords = []
            updatedrecords = []

            self.log.debug('Request made successfully')
            # reconfigure the data to a nice format
            datareturn = json.dumps(xml.parse(datareturn.text))
            datareturn = json.loads(datareturn)
        
            if isinstance(datareturn['report']['row'], dict):
                # only a single record was found, transfrom to list
                datareturn['report']['row'] = [datareturn['report']['row']]
                
            for row in datareturn['report']['row']:
                hashedrecord = self._hash_wrapper(json.dumps(row))
                try:
                    self.reportids[int(row['id'])]
                    
                    if self.reportids[int(row['id'])] != hashedrecord:
                        # changed
                        self.reportids[row['id']] = hashedrecord # update hash
                        updatedrecords.append({'data': row, 'hash': hashedrecord,
                             "timepulled": dt.now().strftime("%Y-%m-%d %H:%M:%S")})
                except KeyError:
                    # doesnt exist. add
                    print('new')
                    self.reportids[row['id']] = hashedrecord
                    self.toupload.append({'data': row, 'hash': hashedrecord})
                    newrecords.append({'data': row, 'hash': hashedrecord, 
                        "timepulled": dt.now().strftime("%Y-%m-%d %H:%M:%S") })

            self.log.info(
                '--------------------------------------------- \n \
                Found {n} new values to be uploaded \n \
                ---------------------------------------------'.format(
                    n=len(updatedrecords) + len(newrecords)))
            
            # add to LS record collection 
            uploads = []
            updates = []
            if newrecords:        
                uploads = await self._db.add_to_db(newrecords)
            if updatedrecords:
                updates = await self._db.update_db(updatedrecords)
      
            # add to the queue
            await self._queue.add_to_queue(uploads, updates)
            self.log.debug('Permanent storage updated')
        
            if uploads or updates:
                return True
            else:
                return False

    async def check_new(self):
        '''wrapper for pull report'''
        newvalues = await self._pull_report()

        return newvalues

    def update_stars_submission(self, caseid, adden):
        '''
        update the record's history of STARS submission

        inputs
        ------
            caseid: int
                STARS record id to be updated

            adden: dict
                new submission receipt. schema
                `
                {
                    "submissionid": "int", // unique id generated for each sub
                    "timestamp": "time", // time submitted
                    "returncode": "string" // response code from STARS server
                }
                '
        '''
        
        self._update_db(record=caseid, key="STARShistory", value=adden)


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
    lsserver = LSClient(auth[0], (auth[1], auth[2]), dbdriver, queue, log)
    
    class MainHandler(tornado.web.RequestHandler):
        async def get(self):
            db = self.settings['db']

            await lsserver.check_new()

            x = await db.fetch_all()

    print('startup')


    application = tornado.web.Application([
        (r'/', MainHandler)
        ], db=dbdriver)

    application.listen(5000)
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    main()