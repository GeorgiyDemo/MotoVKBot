
import pymongo
import datetime

connection_str = ""

mongo_con = pymongo.MongoClient(connection_str)
mongo_db = mongo_con['MotoVKBot']
mongo_col = mongo_db["ttl"]

utc_timestamp = datetime.datetime.utcnow()
utc_timestamp = utc_timestamp + datetime.timedelta(seconds=10)


mongo_col.create_index("date_expire", expireAfterSeconds=0)                     
mongo_col.insert_one({"user_id": "test user", "transition" : "step12to13", "date_expire" : utc_timestamp})