[![License: NCPUL](https://img.shields.io/badge/license-NCPUL-blue.svg)](./LICENSE.md)

# SEPA Income Distribution

Simple Python application that automatically redistributes income (or any positive balance change) from one **source** bank account to multiple **destination** accounts according to minimum-balance rules and configurable surplus-splitting percentages.

> This project automates the process for any European bank that supports **FinTS**.

---

## ✨ Key features

* **FinTS 3.0** connection via [python-fints](https://github.com/raphaelm/python-fints) – works with most German and many EU banks.
* **Rule-based transfers**
  * keep a configurable *minimum balance* on the source account
  * if a destination falls below its *minimum balance*, top it up
  * once the *surplus threshold* is exceeded, distribute the remainder by percentage
* **Flexible scheduling** – run every *n* hours, days, specific day of month, or every second/third/fourth month with offset.
* **External balance sync** – JSON API (built for the [Finanzguru ADB API](https://github.com/yniverz/finanzguru-adb-api)) keeps destination balances up-to-date.
* **TAN workflow** – supports both decoupled (pushTAN/appTAN) and manual input.
* Persists an encrypted FinTS *client data blob* so you do not need to re-authorize with a tan on every run.

---

## 📦 Requirements

| Requirement                                                | Notes                                                                              |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Python 3.9+                                                | Tested with 3.11.                                                                  |
| A German/EU bank that offers FinTS (“HBCI PIN/TAN”) access | You need **BIC**, **BLZ** and **product ID** (sometimes called “FinTS client ID”). |
| Online Banking access                                      | Supporting banks will let you use FinTS with your Online Banking credentials       |

Install dependencies:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # see "Installation" below if the file is missing
```

---

## ⚙️ Configuration

Create `config.json` in the project root. The easiest way is to copy & adapt the sample:

```bash
cp example.config.json config.json
# …edit values …
```

Below is the full annotated example shipped with the repository. Comments (`// …`) explain each field – remove them for a valid JSON file.

```jsonc
{
    "source": {
        "fints": {
            "host": "fints.example.com",         // FinTS endpoint of your bank
            "product_id": "1234567890",          // Any 10-digit ID – ask your bank if unsure
            "account_name": "John Doe",          // Account holder as registered at the bank
            "iban": "DE12345678901234567890",    // IBAN of the **source** account
            "bic": "DEUTDEDBFRA",                // BIC of the bank
            "blz": "12345678",                   // Bankleitzahl (8 digits)
            "username": "john.doe",              // FinTS login / alias
            "password": "password123"            // FinTS PIN (use an env-var or secret store in production!)
        },
        "min_transaction": 50,                      // <EUR> – transfers below this are skipped
        "min_balance": 1000,                        // Keep at least this amount on **source**
        "surplus_threshold": 2000,                  // Start distributing once balance exceeds this
        "interval": "1m1",                          // Scheduler (see next section)
        "start_hour": 22                            // Local hour of day (0-23) to run the job
    },

    // Optional REST endpoint providing **destination** balances as JSON
    "destinations_base_url": "https://api.example.com/destinations",

    "destinations": [
        {
            "name": "Destination 1",                // Friendly name – must be unique
            "account_name": "John Doe",             // Account holder (appears on the transfer)
            "iban": "DE12345678901234567890",       // IBAN of the destination account
            "bic": "DEUTDEDBFRA",                   // BIC of the destination bank
            "min_balance": 1000,                    // Top up until this balance is reached
            "surplus_percentage": 0.5               // Share of surplus (all destinations must add up to 1)
        }
        // ...add more destinations…
    ]
}
```

> **Note** The `destinations_base_url` feature is designed for the [Finanzguru ADB API](https://github.com/yniverz/finanzguru-adb-api) but any endpoint that returns a JSON object of `{ "<Destination-name>": <balance>, "last_update": <unix-timestamp> }` will work.

### Interval syntax

| Format | Meaning                              | Example                                                                               |
| ------ | ------------------------------------ | ------------------------------------------------------------------------------------- |
| `6h`   | Every *n* hours                      | `6h` → every 6 hours at the configured `start_hour`                                   |
| `Xd`   | Every *n* days                       | `3d` → every 3 days                                                                   |
| `XmY`  | Day *Y* of every *nᵗʰ* month         | `1m1` = **1** month cycle **+1** day → run on the **2nd** of every month               |
| `XMY`  | Every 1/ *X* months, offset *Y* days | `2M0` → every **other** month on the 1st; `3M10` → every **three** months on the 11th |

The job is triggered when the interval AND `start_hour` match *local time*. Inside a single run the application sleeps 30 minutes between checks to avoid duplicate executions.

---

## 🚀 Running the application

```bash
python app.py
```

1. On the first start the client connects to the bank and asks for a TAN.
   Decoupled procedures (photoTAN, pushTAN) are detected automatically.
2. A binary `client_data_blob.data` is saved next to the script – **keep this file secure**. It contains the synchronised FinTS keys and avoids full handshake on subsequent runs.
3. The main loop executes according to `interval` and prints a summary of each transfer batch.

---

## 🔒 Security considerations

* **Never commit `config.json`** – add it to your `.gitignore` (already present).
  Use environment variables or a secret manager (e.g. Docker Secrets, systemd ‐ EnvironmentFile) and read them in `config.py` if you need parameter-less deployment.
* Restrict file permissions of `client_data_blob.data` – it contains session-specific keys for your bank.
* The FinTS PIN is stored **in plain text** inside `config.json`. Consider prompting via environment variable or command line in production.

---

## Acknowledgements

* [python-fints](https://github.com/raphaelm/python-fints) – FinTS library
* [Finanzguru ADB API](https://github.com/yniverz/finanzguru-adb-api) – optional balance ingestion.
