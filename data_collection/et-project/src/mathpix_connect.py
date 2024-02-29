import requests
import json
import logging
from config import load_config
from pymongo import MongoClient

config = load_config()

class Mathpix:
    def __init__(self, app_id=config["mathpix"]["app_id"],
                 app_key_api=config["mathpix"]["app_api_key"],
                 mongo_connect=config["mongodb"]["uri"]):
        self.app_id = app_id
        self.app_api_key = app_key_api
        self.client = MongoClient(mongo_connect)
    
    def checkOne(self, file=None):
        if file == None:
            logging.error("Cropped image doesn't exist, can't send to mathpix")
            print("File doesn't exist")
            return
        
        result = None

        with open(file, 'rb') as img: 
            r = requests.post("https://api.mathpix.com/v3/text", 
                files={"file": img},
                data={
                    "options_json": json.dumps({
                        "math_inline_delimiters": ["$", "$"],
                        "rm_spaces": True
                    })
                },
                headers={
                    "app_id": self.app_id,
                    "app_key": self.app_api_key
                }
            )

            result = json.loads(r.text)
            print(result)
        
        return result
    
    def storeMongo(self, file=None):
        if file == None:
            logging.error("Cropped image doesn't exist, can't send to mathpix")
            print("File doesn't exist")
            return
        
        mp_result = self.checkOne(file)

        result = {"question": mp_result["text"]}
        # database and collection code goes here
        db = self.client.Edtorch
        coll = db.question
        coll.insert_one(result)



