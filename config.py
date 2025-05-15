import datetime
import json
import math
import re
from typing import Union

# {
#     "source": {
#         "fints": {
#             "host": "fints.example.com",
#             "product_id": "1234567890",
#             "account_name": "John Doe",
#             "iban": "DE12345678901234567890",
#             "bic": "DEUTDEDBFRA",
#             "blz": "12345678",
#             "username": "john.doe",
#             "password": "password123"
#         },
#         "min_transaction": 50,          // minimum amount before transaction is submitted
#         "min_balance": 1000,            // minimmum balance to keep on source
#         "surplus_threshold": 2000,      // (optional) amount after which the surplus is distributed by percentage
#         "interval": "1d"                // interval to check for actions (6h: every 6 hours, Xd: every X days, Xm: every X months, Xmm: every 1/X months with X between 2 and 4)
#     },
#     "destinations_url": "https://api.example.com/destinations", // url to fetch destinations from (dict of name=>balance and "last_updated"=>timestamp)
#     "destinations": [
#         {
#             "name": "Destination 1",
#             "account_name": "John Doe",
#             "iban": "DE12345678901234567890",
#             "bic": "DEUTDEDBFRA",
#             "min_balance": 1000,        // minimum balance to fill up to from source
#             "surplus_percentage": 0.5   // (required if surplus_threshold set) percentage of surplus to distribute to this destination (all destinations must add up to 1)
#         }
#     ]
# }





class SourceFintsData:
    def __init__(self, host: str, product_id: str, account_name: str, iban: str, bic: str, blz: str, username: str, password: str):
        self.host = host
        self.product_id = product_id
        self.account_name = account_name
        self.iban = iban
        self.bic = bic
        self.blz = blz
        self.username = username
        self.password = password

class Source:
    def __init__(self, fints: SourceFintsData, min_transaction: int = 0, min_balance: int = 0, surplus_threshold: int = None, interval: str = "1d"):
        if min_transaction < 0:
            raise ValueError("Minimum transaction must be greater than or equal to 0")
        if min_balance < 0:
            raise ValueError("Minimum balance must be greater than or equal to 0")
        if surplus_threshold and surplus_threshold < 0:
            raise ValueError("Surplus threshold must be greater than or equal to 0")
        if not re.match(r"^(6h|[0-9]+d|[0-9]+m|[2-4]mm)$", interval):
            raise ValueError("Interval must be in the format 'Xd', 'Xh' or 'Xm' where X is a positive integer, or 'Xmm' where X is a positive integer between 2 and 4")
        
        self.fints = fints
        self.min_transaction = min_transaction
        self.min_balance = min_balance
        self.surplus_threshold = surplus_threshold
        self.interval = interval




class Destination:
    def __init__(self, name: str, account_name: str, iban: str, bic: str, min_balance: int = 0, surplus_percentage: float = 0.0):
        if min_balance < 0:
            raise ValueError("Minimum balance must be greater than or equal to 0")
        if surplus_percentage < 0 or surplus_percentage > 1:
            raise ValueError("Surplus percentage must be between 0 and 1")
        
        self.name = name
        self.account_name = account_name
        self.iban = iban
        self.bic = bic
        self.min_balance = min_balance
        self.surplus_percentage = surplus_percentage


class Config:
    def __init__(self, filename: str = "config.json"):
        self.filename = filename

        self.source = None
        self.destinations_url = None
        self.destinations = []

        self.load()

    def load(self):
        try:
            self._load()
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file {self.filename} not found. Use example.config.json to create a new one.")
        except Exception as e:
            # shutil.copyfile(self.filename, self.filename + "." + str(int(time.time())) + ".bak")
            raise Exception(f"Error loading config file {self.filename}: {e}")
        
    def _load(self):
        with open(self.filename, "r") as f:
            data: dict[str, Union[dict, list, str]] = json.load(f)
            self.source = Source(
                fints=SourceFintsData(
                    host=data["source"]["fints"]["host"],
                    product_id=data["source"]["fints"]["product_id"],
                    account_name=data["source"]["fints"]["account_name"],
                    iban=data["source"]["fints"]["iban"],
                    bic=data["source"]["fints"]["bic"],
                    blz=data["source"]["fints"]["blz"],
                    username=data["source"]["fints"]["username"],
                    password=data["source"]["fints"]["password"]
                ),
                min_transaction=data["source"].get("min_transaction", 0),
                min_balance=data["source"].get("min_balance", 0),
                surplus_threshold=data["source"].get("surplus_threshold"),
                interval=data["source"].get("interval", "1d")
            )
            self.destinations_url = data["destinations_url"]
            self.destinations = [
                Destination(
                    name=destination["name"],
                    account_name=destination["account_name"],
                    iban=destination["iban"],
                    bic=destination["bic"],
                    min_balance=destination["min_balance"],
                    surplus_percentage=destination.get("surplus_percentage", 0)
                )
                for destination in data["destinations"]
            ]
            if len(self.destinations) == 0:
                raise ValueError("destinations must not be empty")
            if self.source.surplus_threshold and sum([d.surplus_percentage for d in self.destinations]) != 1:
                raise ValueError("Surplus percentages must add up to 1")
            if self.source.surplus_threshold and self.source.surplus_threshold < self.source.min_balance:
                raise ValueError("Surplus threshold must be greater than minimum balance")