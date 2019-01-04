from datetime import datetime as dt

class QueueRunner(object):
    def __init__(self, collection, log):
        self._col = collection
        self.log = log

    async def add_to_queue(self, newrecords, updatedrecords):
        ''' add records to a queue collection with type and record

            inputs
            ------
                newrecords: list of dicts
                    records to be inserted into STARS

                updatedrecords: list of dict
                    records to be updated into STARS
        '''
        queue = []
        for record in newrecords:
            tmp = {
                'type': 'insert',
                'data': record['LShistory'][-1]['data'],
                'hash': record['lasthash'],
                'timeadded': dt.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            queue.append(tmp)

        for record in updatedrecords:
            tmp = {
                'type': 'update',
                'data': record['diff'],
                'hash': record['hash'],
                'timeadded': dt.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            queue.append(tmp)
        
        await self._insert_records(queue)
        self.log.debug('{} items added to queue'.format(len(queue)))

    async def pop_from_queue(self):
        ''' finds first value in the queue, loads it, removes it
            and finally returns it. 

            returns
            -------
                nextrecord: dict
                    first entry in the queue. schema:
                        {
                            "type": "insert/update",
                            "data": {data},
                            "timeadded": datetime added, 
                            "hash": hash(data)
                        }
        '''

        doc = await self._col.find_one({}, max_time_ms=20)
        try:
            await self._col.delete_many({'_id': {'$eq': doc['_id']}})
        except TypeError:
            # will happen when the find timeout occurs. usually means
            # that nothing was found in the queue
            doc = None
        return doc

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
        except:
            pass


def main():
    import tornado.web
    import tornado.autoreload
    from queuerunner import QueueRunner
    from lsdatabasedriver import LSDBDriver
    import motor 
    import logging
    import json
    import time

    tornado.autoreload.start()
    default_path='configs/logconfig.json'
    default_level=logging.INFO

    client = motor.motor_tornado.MotorClient('localhost', 27017)
    db = client.TLSC.testqueue
    
    schema = 'configs/LSschema.json'
    dbdriver = LSDBDriver(db, schema)

    with open(default_path, 'r') as f:
        config = json.load(f)

    logging.config.dictConfig(config)
    log = logging.getLogger(__name__)

    queue = QueueRunner(db.Queue, log)

    class MainHandler(tornado.web.RequestHandler):
        async def get(self):
            db = self.settings['db']

            await queue.add_to_queue(
                [{"LShistory" : [{'data': "new"}], 
                "lasthash": "adfdafasd"}],

                [{"diff" : {"field": "update"}, 
                "hash": "ajfadh"}]
    
            )
            print('added to queue')
            time.sleep(5)
            val = await queue.pop_from_queue()
            print('{} removed from queue'.format(val))
            
            val = await queue.pop_from_queue()
            print('{} removed from queue'.format(val))

            # should return none
            val = await queue.pop_from_queue()
            print('{} removed from queue'.format(val))
    
    application = tornado.web.Application([
        (r'/', MainHandler)
        ], db=dbdriver)

    application.listen(5000)
    tornado.ioloop.IOLoop.current().start()

if __name__ == '__main__':
    main()