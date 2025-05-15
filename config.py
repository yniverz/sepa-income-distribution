import datetime
import json
import math
import re
from typing import Union


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
    def __init__(self, fints: SourceFintsData, min_transaction: int = 0, min_balance: int = 0, surplus_threshold: int = None, interval: str = "1d", start_hour: int = 12):
        if min_transaction < 0:
            raise ValueError("Minimum transaction must be greater than or equal to 0")
        if min_balance < 0:
            raise ValueError("Minimum balance must be greater than or equal to 0")
        if surplus_threshold and surplus_threshold < 0:
            raise ValueError("Surplus threshold must be greater than or equal to 0")
        if not re.match(r"^(6h|[0-9]+d|[0-9]+m(?:[1-9]|[1-2][0-9]|3[0-1])|[2-4]M(?:[1-9]|[1-2][0-9]|3[0-1]))$", interval):
            raise ValueError("Interval must be in the format '6h' 'Xd' or 'XmY' where X is a positive integer, or 'XMY' where X is a positive integer between 2 and 4 and Y is the offset in days since the start of the month (0-31)")
        if start_hour < 0 or start_hour > 23:
            raise ValueError("Start hour must be between 0 and 23")
        
        self.fints = fints
        self.min_transaction = min_transaction
        self.min_balance = min_balance
        self.surplus_threshold = surplus_threshold
        self.interval = interval
        self.start_hour = start_hour

        self.last_action_time: datetime.datetime = None

    def is_interval_reached(self, tz=None) -> bool:
        if self._is_interval_reached(tz):
            self.last_action_time = datetime.datetime.now(tz)
            return True
        
        return False

    def _is_interval_reached(self, tz=None) -> bool:
        now = datetime.datetime.now(tz)
        if self.interval.endswith("h") or self.interval.endswith("d"):
            if self.last_action_time is None or now - self.last_action_time >= interval - datetime.timedelta(hours=1):
                return self.start_hour == now.hour

        parts = self.interval.lower().split("m")
        interval_digit = int(parts[0])
        offset_digit = int(parts[1]) # in days

        if "m" in self.interval:
            start_of_month = now.replace(day=1)
            month = start_of_month + datetime.timedelta(days=offset_digit)
            if start_of_month.month != month.month:
                month = month.replace(day=1)
                month -= datetime.timedelta(days=1)

            interval = datetime.timedelta(days=28*interval_digit)
            if self.last_action_time is None or now - self.last_action_time >= interval - datetime.timedelta(hours=1):
                return month.day == now.day and self.start_hour == now.hour
            
            return False
        
        if "M" in self.interval:
            start_of_month = now.replace(day=1)
            month = start_of_month + datetime.timedelta(days=offset_digit)
            if start_of_month.month != month.month:
                month = month.replace(day=1)
                month -= datetime.timedelta(days=1)

            if month.day == now.day and self.start_hour == now.hour and now - self.last_action_time >= datetime.timedelta(hours=2):
                return True

            if self.last_action_time is None or now - self.last_action_time >= interval - datetime.timedelta(minutes=10):
                return self.start_hour == now.hour
            
            return False

        raise ValueError("Interval must be in the format '6h' 'Xd' or 'XmY' where X is a positive integer, or 'XMY' where X is a positive integer between 2 and 4 and Y is the offset in days since the start of the month (0-31)")


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