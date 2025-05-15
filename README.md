# sepa-income-distribution
Simple Python application that can distribute money from European Banks based on custom criteria

config example:
```json
{
    "source": {
        "fints": {
            "host": "fints.example.com",
            "product_id": "1234567890",
            "account_name": "John Doe",
            "iban": "DE12345678901234567890",
            "bic": "DEUTDEDBFRA",
            "blz": "12345678",
            "username": "john.doe",
            "password": "password123"
        },
        "trigger": {                  // triggers to distribute money (will be "and"ed)
            "threshold": 10000,           // amount above which to distribute (essentially a minimum balance)
            "delta_threshold": 100,       // (optional) amount above threshold to trigger distribution
            "events": [
                {                     // (optional) date based events to trigger distribution
                    "type": "monthly",    // type of event: monthly, weekly, daily
                    "day": 1,             // day of month to trigger distribution (1-31) or day of week (1-7, 7=Monday)
                    "time": "12:00"       // time of day to trigger distribution (HH:MM)
                }
            ]
        }
    },
    "destinations_url": "https://api.example.com/destinations", // url to fetch destinations from (dict of name=>balance and "last_updated"=>timestamp)
    "destinations": [
        {
            "name": "Destination 1",
            "account_name": "John Doe",
            "iban": "DE12345678901234567890",
            "bic": "DEUTDEDBFRA",
            "amount": {               // amount to distribute on trigger
                "type": "fill_up",        // type of amount: fixed, percentage, fill_up (will fill balance up to value)
                "value": 1000             // value of amount to distribute/fill up to
            }
        }
    ]
}
```