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
        "min_transaction": 50,          // minimum amount before transaction is submitted
        "min_balance": 1000,            // minimmum balance to keep on source
        "surplus_threshold": 2000,      // amount after which the surplus is distributed by percentage
        "interval": "1d"                // interval to check for actions (6h: every 6 hours, Xd: every X days, Xm: every X months, Xmm: every 1/X months with X between 2 and 4)
    },
    "destinations_url": "https://api.example.com/destinations", // url to fetch destinations from (dict of name=>balance and "last_updated"=>timestamp)
    "destinations": [
        {
            "name": "Destination 1",
            "account_name": "John Doe",
            "iban": "DE12345678901234567890",
            "bic": "DEUTDEDBFRA",
            "min_balance": 1000,        // minimum balance to fill up to from source
            "surplus_percentage": 0.5   // percentage of surplus to distribute to this destination (all destinations must add up to 1)
        }
    ]
}
```