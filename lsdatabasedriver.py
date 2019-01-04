import json
from jsmin import jsmin
import logging.config
from datetime import datetime as dt
from pymongo import InsertOne, UpdateOne
import motor
from pymongo.errors import BulkWriteError

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
        self._queue = db.Queue
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
            r = await self._col.find_one({'caseid': {'$eq': int(record)}}, projection)
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
            # append to history field and update hash
            query = {'caseid': {'$eq': int(record['data']['id'])} }
            updatehistory ={'$push': {'LShistory' : record}}
            updatehash = {'$set': {'lasthash': record['hash']}}
            requests.append( UpdateOne(query, updatehistory) )
            requests.append( UpdateOne(query, updatehash) )

        result = await self._col.bulk_write(requests)
        print(result.bulk_api_result)

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

        uploads = []
        for record in records:
            tmp = self.schema.copy()
            tmp['caseid'] = int(record['data']['id'])
            tmp['LShistory'] = [{
                'timepulled': record['timepulled'],
                'hash': record['hash'],
                'data': record['data']
            }]
            tmp['lasthash'] = record['hash']
            
            uploads.append(tmp)

        # push to db
        await self._insert_records(uploads)

        return uploads

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
        for record in oldrecordlist:
            key = str(record['caseid'])
            recordhistory[key] = record['LShistory'][-1]['data'] # LShistory is list

        print('record hist', recordhistory)
        for record in records:
            key = record['data']['id']
            diff = self._dict_compare(recordhistory[key], 
                record['data'])
            record['diff'] = diff
            updates.append(record)
        
        await self._update_records(updates)

        return updates

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
            documents[doc['caseid']] = doc['lasthash']

        return documents

