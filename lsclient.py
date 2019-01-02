import requests as rq
import json
import xmltodict as xml
import logging
from hashlib import sha224

from jsmin import jsmin
import logging.config
from datetime import datetime as dt
from pymongo import InsertOne, DeleteMany, ReplaceOne, UpdateOne, 


class LSClient(object):
    def __init__(self, apikey, auth, permstore, schema, log):

        '''
        inputs:
        -------
            apikey: str
                url corresponding to the report XML API
            
            auth: tuple of strings
                (username, password) for http authentication
                
            permstore: str
                filelocation where the uploaded ids can be stored 
                persistently in case of shutdown

            schema: str
                filelocation of database schema in JSON.
                will be minified, so comments are kosher
            
            log: logging log
                log to store runs and id updates
            
        parameters:
        -----------
            reportids: dict
                all the report IDs that have already been uploaded
                {"caseid": ID, "lasthash": str(hash)}
                
            toupload: list of dicts
                row object returned by requests that are not in reportids
                (i.e. the need to be uploaded)      
        '''
        
        self.apikey = apikey
        self.auth = auth
        self.permstore = permstore
        self.schema = schema
        self.log = log
        self._recorddb = recorddb
        self._queuedb = queue
    
        self.reportids = []
        self.toupload = []
        self.newrecords = []

        # run initalizations
        self._load_schema()
        self._id_check()
    
    def _load_schema(self):
        ''' loads server schema from json config file. pipes through jsmin
            to allow for inline comments in JSON '''

            with open(self.schema, 'r') as f:
                self.schema = json.loads(jsmin(f.read()))
        
    def _id_check(self):
        ''' open the file where the permstore is and check if it is empty.
            run once on startup to minimize queries to the database'''
        
        try:
            with open(self.permstore, 'r') as f:
                tmp = f.readlines()

            self.reportids = [int(line) for line in tmp]
        except OSError:
            self.log.debug('File Not Found Error. Creating file at {}'.format(self.permstore))
            
            with open(self.permstore, 'w+') as f:
                pass
 
    def _hash_wrapper(self, string):
        '''wrapper to save the single step of .encode(utf-8)'''
        return sha224(bytes(string.encode("utf-8"))).hexdigest()
   
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

    def _pull_report(self):
        '''
        pull the report using requesets. authentication handled using http auth
        '''
        self.log.debug('Attempting to make request')
        datareturn = rq.get(self.apikey, auth=(self.auth[0], self.auth[1]))

        # check datareturn error codes
        if datareturn.status_code != 200:
            print(datareturn.status_code)
            self.log.debug('Bad request. Error code: {}'.format(datareturn.status_code))
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
                    
                    if self.reportids[row['id']]['data']['hash'] != hashedrecord:
                        # changed
                        self.reportids[row['id']]['data']['hash'] = hashedrecord # update hash
                        self.reportids[row['id']]['data']['modified'] = dt.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.toupload.append({'data': row, 'hash': hashedrecord})
                        
                except KeyError:
                    # doesnt exist. add
                    self.reportids[row['id']] = {"data": { 'hash': hashedrecord}}
                    self.reportids[row['id']]['data']['modified'] = dt.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.toupload.append({'data': row, 'hash': hashedrecord})
                    newrecords.append({'data': row, 'hash': hashedrecord})

            self.log.info(
                '--------------------------------------------- \n \
                Found {n} new values to be uploaded \n \
                ---------------------------------------------'.format(n=len(self.toupload)))
            
            # TODO
            # self._add_to_db()
            with open(self.permstore, 'w') as f:
                f.write(json.dumps(self.reportids))
            
            self.log.debug('Permanent storage updated')
        

    def _add_to_db(self, records):
        ''' formats NEW records and updates to the database

            inputs
            ------
                records: list of dicts
                    new records to be uploaded to db. schema
                    {"data": dict from LS, "hash": hashvalue}


        '''
        upload = []
        for record in records:
            tmp = self.schema
            tmp['caseid'] = int(record['data']['id'])
            tmp['LShistory'] = {
                'timepulled': dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                'hash': record['hash'],
                'record': record['data']
            }
            upload.append(tmp)
        
        # push to db
        self._recorddb.insert_many(upload)


    def _update_db(self, records):
        ''' update an existing record in the LS database. will pull old records
            from database, load into memory, compare values, and finally 
            upload edits.

        inputs
        ------
            records: list of dicts
                updated records to be uploaded to db. schema
                {"data": dict from LS, "hash": hashvalue}
        '''
        updates = []
        
        # fetch old records
        recordids = [r['data']['id'] for r in recordids] 
        oldrecords = self._fetchrecords(recordids)

        for record in records:
            diff = self._dict_compare(oldrecords)   

    async def _fetchrecords(self, recordids):
        c = db.test_collection

        documents = []
        for record in recordids:
            r = await self._recorddb.find_one({'caseid': {'$eq': record}})
            documents.append(r)

        return documents

    def check_new(self):
        '''wrapper for pull report'''
        self._pull_report()

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

        