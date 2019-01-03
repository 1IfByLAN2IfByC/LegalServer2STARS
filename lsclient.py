import requests as rq
import json
import xmltodict as xml
import logging
from hashlib import sha224
import asyncio 

from jsmin import jsmin
import logging.config
from datetime import datetime as dt
from pymongo import InsertOne, UpdateOne
import motor
from pymongo.errors import BulkWriteError


class LSClient(object):
    def __init__(self, apikey, auth, db, log):

        '''
        inputs:
        -------
            apikey: str
                url corresponding to the report XML API
            
            auth: tuple of strings
                (username, password) for http authentication
                
            db: LSDBDriver
                database to store LS logs
            
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
        # self._queuedb = queue
    
        self.reportids = []
        self.toupload = []
        self.newrecords = []

    async def startup(self):
        await self._id_check()
        
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
                    self.reportids[row['id']]
                    
                    if self.reportids[row['id']] != hashedrecord:
                        # changed
                        self.reportids[row['id']] = hashedrecord # update hash
                        self.toupload.append({'data': row, 'hash': hashedrecord})
                        updatedrecords.append({'data': row, 'hash': hashedrecord,
                             "timepulled": dt.now().strftime("%Y-%m-%d %H:%M:%S")})
                        
                except KeyError:
                    # doesnt exist. add
                    self.reportids[row['id']] = hashedrecord
                    self.toupload.append({'data': row, 'hash': hashedrecord})
                    newrecords.append({'data': row, 'hash': hashedrecord, 
                        "timepulled": dt.now().strftime("%Y-%m-%d %H:%M:%S") })

            self.log.info(
                '--------------------------------------------- \n \
                Found {n} new values to be uploaded \n \
                ---------------------------------------------'.format(n=len(self.toupload)))
            await self._db.add_to_db(newrecords)
            # self._db._update_db(updatedrecords)
      
            self.log.debug('Permanent storage updated')
        
    async def check_new(self):
        '''wrapper for pull report'''
        await self._pull_report()

        return self.toupload

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


class LSDBDriver(object):
    ''' Driver for connecting to a mongo database and performing LS queries'''

    def __init__(self, db, schema):
        '''
        inputs
        ------
            db: motor.AsyncIOMotorClient.database
                collection for operations to be performed on 

            schema: str
                filelocation of database schema in JSON.
                will be minified, so comments are kosher
        '''

        self._col = db.LegalServer
        self.schema = schema
        self.db = db

        self._load_schema()
    def _load_schema(self):
        ''' loads server schema from json config file. pipes through jsmin
            to allow for inline comments in JSON '''
        with open(self.schema, 'r') as f:
            self.schema = json.loads(jsmin(f.read()))

    async def _fetch_records(self, recordids):
        ''' fetch many records where the record id matches input

            inputs
            ------
                recordids: list of ints
                    record ids to fetch
            
            returns
            -------
                documents: list of dicts
                    list of returned records
        '''
        projection = { "_id": 0} 
        documents = []
        for record in recordids:
            r = await self._col.find_one({'caseid': {'$eq': record}}, projection)
            documents.append(r)

        return documents
    
    async def _insert_records(self, records):
        ''' insert multiple records into the database

            inputs
            ------
                records: list of dicts
                    records to be inserted
        '''
        try:
            for record in records:
                # not sure why i am having to manually do this
                if '_id' in record:
                    del record['_id']
                await self._col.insert_one(record)

        except BulkWriteError as bwe:
            print(bwe.details)
            
    async def _update_records(self, records):
        ''' updates many records in LS database

            inputs
            ------
                records: list of dicts
                    records to be updated. schema: {
                        "data": {LS pull}, 
                        "hash":str(hashed value), 
                        "diff": {difference with last},
                        "timepulled": str(timestamp)
                    }
        '''
        requests = []

        for record in records:
            # append to history field
            query = { {'caseid': record['data']['caseid']}, 
                {'$push': {'LShistory' : record} } }

            requests.append(UpdateOne(query))
        
        await self._col.bulk_write(requests)

    def _dict_compare(self, a, b):
        ''' compare the values for two dictionaries with the same keys. will 
            return a dictionary of the difference

            used to find which of the key, value pairs needs to be updated
            in the records, where b is assumed to be the newer record.

            inputs
            ------
                a, b: dict
                    dictionaries to compare

            returns
            -------
                diff: dict
                    difference between a and b (a->b)
        '''

        old = set(a.items())
        new = set(b.items())

        return dict(new-old)

    async def add_to_db(self, records):
        ''' formats NEW records and updates to the database

            inputs
            ------
                records: list of dicts
                    new records to be uploaded to db. schema
                    {"data": {LS rec}, "hash": "hashvalue", "timepulled": "timestamp"}
        '''

        upload = []
        for record in records:
            tmp = self.schema.copy()
            tmp['caseid'] = int(record['data']['id'])
            tmp['LShistory'] = {
                'timepulled': record['timepulled'],
                'hash': record['hash'],
                'data': record['data']
            }
            tmp['lasthash'] = record['hash']
            
            upload.append(tmp)

        # push to db
        await self._insert_records(upload)

    async def update_db(self, records):
        ''' update an existing record in the LS database. will pull old records
            from database, load into memory, compare values, and finally 
            upload edits.

        inputs
        ------
            records: list of dicts
                records to be updated. schema: {
                    "data": {LS pull}, 
                    "hash": str(hashed value), 
                    "timepulled": str(timestamp)
                    }
        '''

        updates = []
        # fetch old records
        recordids = [r['data']['id'] for r in records] 
        oldrecordlist = await self._fetch_records(recordids)
        # restructure oldrecords to be dict where id is key
        recordhistory= {}
        for record in records:
            key = record['data']['id']
            recordhistory[key] = record['LShistory'][-1] # LShistory is list

        for record in records:
            key = record['data']['id']
            diff = self._dict_compare(recordhistory[key], 
                record['data'])
            record['diff'] = diff
            updates.append(record)
        
        [print(r['caseid'], 'outside') for r in records]
        await self._update_records(updates)

    async def fetch_all(self):
        ''' grab all record ids and hashes from the database
        
            returns
            -------
                documents: dict
                    all documents in db. schema: {id: str(hash)} 
        '''

        projection = {"caseid": 1, "lasthash": 1, "_id": 0} 
        documents = {}

        async for doc in self._col.find({}, projection):
            print('from db', doc)
            documents[doc['caseid']] = doc['lasthash']

        return documents


def main():
    import tornado.web
    import tornado.autoreload
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
        
    lsserver = LSClient(auth[0], (auth[1], auth[2]), dbdriver, log)
    class MainHandler(tornado.web.RequestHandler):
        async def get(self):
            db = self.settings['db']

            await lsserver.startup()
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