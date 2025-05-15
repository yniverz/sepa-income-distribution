import datetime
import json
import math
import re

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
#         "trigger": {                  // triggers to distribute money (will be "and"ed)
#             "threshold": 10000,           // amount above which to distribute (essentially a minimum balance)
#             "delta_threshold": 100,       // (optional) amount above threshold to trigger distribution
#             "events": [
#                 {                     // date based events to trigger distribution
#                     "type": "monthly",    // type of event: monthly, weekly, daily
#                     "day": 1,             // day of month to trigger distribution (1-31) or day of week (1-7, 7=Monday)
#                     "time": "12:00"       // time of day to trigger distribution (HH:MM)
#                 }
#             ]
#         }
#     },
#     "destinations_url": "https://api.example.com/destinations",
#     "destinations": [
#         {
#             "name": "Destination 1",
#             "account_name": "John Doe",
#             "iban": "DE12345678901234567890",
#             "bic": "DEUTDEDBFRA",
#             "amount": {               // amount to distribute on trigger
#                 "type": "fill_up",        // type of amount: fixed, percentage, fill_up (will fill balance up to value)
#                 "value": 1000             // value of amount to distribute/fill up to
#             }
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
        
class TriggerEventType:
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"

class TriggerEvent:
    def __init__(self, event_type: TriggerEventType, day: int, time: str = "12:00"):
        if event_type not in TriggerEventType.__dict__.values():
            raise ValueError("Invalid event type")
        self.event_type = event_type
        
        if event_type == TriggerEventType.MONTHLY and (day < 1 or day > 31):
            raise ValueError("Day must be between 1 and 31 for monthly events")
        elif event_type == TriggerEventType.WEEKLY and (day < 1 or day > 7):
            raise ValueError("Day must be between 1 and 7 for weekly events")
        self.day = day
        
        if not re.match(r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$", time):
            raise ValueError("Time must be in HH:MM 24h format")
        self.time = time

        self.last_triggered = None

    def is_triggered(self, tz=None):
        now = datetime.datetime.now(tz)

        if self.last_triggered is not None and (now - self.last_triggered).total_seconds() < 65:
            return False

        if self.event_type == TriggerEventType.MONTHLY:
            if self.last_triggered.month != now.month:
                if now.day == self.day and now.strftime("%H:%M") == self.time:
                    self.last_triggered = now
                    return True
        elif self.event_type == TriggerEventType.WEEKLY:
            if self.last_triggered.isocalendar()[1] != now.isocalendar()[1]:
                if now.isocalendar()[2] == self.day and now.strftime("%H:%M") == self.time:
                    self.last_triggered = now
                    return True
        elif self.event_type == TriggerEventType.DAILY:
            if now.strftime("%H:%M") == self.time:
                self.last_triggered = now
                return True
        return False

class Trigger:
    def __init__(self, threshold: int, delta_threshold: int = None, events: list[TriggerEvent] = []):
        if threshold <= 0:
            raise ValueError("Threshold must be greater than 0")
        self.threshold = threshold
        if delta_threshold is not None and delta_threshold <= 0:
            raise ValueError("Delta threshold must be greater than 0")
        self.delta_threshold = delta_threshold
        self.events = events

    def is_triggered(self, balance: int, tz=None):
        if balance < self.threshold:
            return False

        if self.delta_threshold is not None and balance < self.threshold + self.delta_threshold:
            return False

        if not self.events:
            return True

        is_triggered = False
        for event in self.events:
            is_triggered = is_triggered or event.is_triggered(tz)
        
        return is_triggered

class Source:
    def __init__(self, fints: SourceFintsData, trigger: Trigger):
        self.fints = fints
        self.trigger = trigger

class DestinationAmountType:
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    FILL_UP = "fill_up"

class DestinationAmount:
    def __init__(self, amount_type: DestinationAmountType, value: int):
        if amount_type not in DestinationAmountType.__dict__.values():
            raise ValueError("Invalid amount type")
        self.amount_type = amount_type
        if value <= 0:
            raise ValueError("Value must be greater than 0")
        self.value = value

    def get_amount(self, source: Source, source_balance: int, destination_balance: int):
        if self.amount_type == DestinationAmountType.FIXED:
            return self.value
        elif self.amount_type == DestinationAmountType.PERCENTAGE:
            delta = source_balance - source.trigger.threshold
            if delta < 0:
                return 0
            return math.floor(delta * (self.value / 100))
        elif self.amount_type == DestinationAmountType.FILL_UP:
            return math.floor(max(0, self.value - destination_balance), 2)
        else:
            raise ValueError("Invalid amount type")


class Destination:
    def __init__(self, name: str, account_name: str, iban: str, bic: str, amount: DestinationAmount):
        self.name = name
        self.account_name = account_name
        self.iban = iban
        self.bic = bic
        self.amount = amount


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
            data: dict = json.load(f)
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
                trigger=Trigger(
                    threshold=data["source"]["trigger"]["threshold"],
                    delta_threshold=data["source"]["trigger"].get("delta_threshold"),
                    events=[
                        TriggerEvent(
                            event_type=event["type"],
                            day=event["day"],
                            time=event.get("time", "12:00")
                        ) for event in data["source"]["trigger"].get("events", [])
                    ]
                )
            )
            self.destinations_url = data["destinations_url"]
            self.destinations = [
                Destination(
                    name=dest["name"],
                    account_name=dest["account_name"],
                    iban=dest["iban"],
                    bic=dest["bic"],
                    amount=DestinationAmount(
                        amount_type=dest["amount"]["type"],
                        value=dest["amount"]["value"]
                    )
                ) for dest in data.get("destinations", [])
            ]