import os
import time
import traceback
import uuid
from fints.client import FinTS3PinTanClient, NeedTANResponse, ResponseStatus, SEPAAccount
import requests

from config import Config, Destination



def do_tan(needTanResponse: NeedTANResponse):
    if needTanResponse.decoupled:
        while isinstance(client.send_tan(needTanResponse, None), NeedTANResponse):
            time.sleep(2)
    else:
        res = client.send_tan(needTanResponse, input("Tan: "))
        if isinstance(res, NeedTANResponse):
            print("Not authorized. Exiting...")
            exit(1)

def do_transfer(config: Config, client: FinTS3PinTanClient, source_account: SEPAAccount, destination: Destination, amount: float):
    print("transfering " + str(amount) + " EUR to " + destination.name + " (" + destination.iban + ")")

    print("Doing transfer...")

    transfer = client.simple_sepa_transfer(
        account=source_account,
        iban=destination.iban, 
        bic=destination.bic, 
        recipient_name=config.source.fints.account_name, 
        amount=amount, 
        account_name=config.source.fints.account_name, 
        reason="Automatic Transfer "+str(round(time.time())), 
        instant_payment=True,
        endtoend_id=uuid.uuid4().hex
    )

    if isinstance(transfer, NeedTANResponse):
        do_tan(transfer)
    
    print(transfer.status)
    print(transfer.responses)

    if transfer.status == ResponseStatus.ERROR:
        raise "Transfer failed\n\n"+str(transfer.responses)

def get_current_balances(config: Config):
    destination_balances = requests.get(config.destinations_base_url + "accounts").json()

    if destination_balances["last_update"] < time.time() - 60*60:
        print("Destination balances are older than 1 hour. Updating...")
        
        requests.get(config.destinations_base_url + "request_update")

        time.sleep(1)

        print("Waiting for update to finish...")

        while True:
            update_running = requests.get(config.destinations_base_url + "update_running").json()
            if update_running["status"] == "ok":
                break

            time.sleep(5)

        return requests.get(config.destinations_base_url + "accounts").json()
    
    return destination_balances

def do_checks(config: Config, client: FinTS3PinTanClient, source_account: SEPAAccount):
    # Get the balance of the source account
    balance = client.get_balance(source_account).amount.amount
    print(f"Balance: {balance}")

    # Check if the balance is above the minimum balance
    if balance < config.source.min_balance:
        print(f"Balance {balance} is below minimum {config.source.min_balance}. No transfer possible.")
        return

    destination_balances = get_current_balances(config)

    sum_delta = 0
    for destination in config.destinations:
        if destination.name not in destination_balances:
            print(f"Destination {destination.name} not found in the response.")
            continue

        destination_balance = destination_balances[destination.name]
        print(f"Destination {destination.name} balance: {destination_balance}")

        if destination_balance > destination.min_balance:
            print(f"Destination {destination.name} balance is above minimum. No transfer needed.")
            continue

        delta = round(destination.min_balance - destination_balance)

        if delta < config.source.min_transaction:
            print(f"Delta {delta} is below minimum transaction. No transfer needed.")
            continue

        do_transfer(config, client, source_account, destination, delta)
        
        sum_delta += delta
            
        time.sleep(10)

    print(f"Sum of deltas: {sum_delta}")

    sum_surplus_transfered = 0
    if config.source.surplus_threshold and balance - sum_delta > config.source.surplus_threshold and (balance - sum_delta) - config.source.min_balance:
        print(f"Surplus {balance - sum_delta} is above threshold {config.source.surplus_threshold}. Distributing surplus.")

        surplus = round(balance - sum_delta - config.source.min_balance)

        for destination in config.destinations:
            delta = round(surplus * destination.surplus_percentage)

            if delta < config.source.min_transaction:
                print(f"Delta {delta} is below minimum transaction. No transfer needed.")
                continue

            do_transfer(config, client, source_account, destination, delta)

            sum_surplus_transfered += delta
            
            time.sleep(10)


    print(f"Total surplus transfered: {sum_surplus_transfered}")
    print(f"Total transfered: {sum_delta + sum_surplus_transfered}")
    print(f"New balance: {balance - sum_delta - sum_surplus_transfered}")

def loop(config: Config, client: FinTS3PinTanClient, source_account: SEPAAccount):
    while True:
        try:
            if config.source.is_interval_reached():
                print("Interval reached. Doing checks...")
                with client:
                    do_checks(config, client, source_account)

            print("Waiting for next interval...")
            time.sleep(60*30)

        except KeyboardInterrupt:
            print("Exiting...")
            break
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error: {e}")
            time.sleep(60*5)
            continue

if __name__ == "__main__":

    # Load the configuration
    config = Config()

    from_data = None
    if os.path.exists("client_data_blob.data"):
        with open("client_data_blob.data", "rb") as f:
            from_data = f.read()
            print("Loaded client data blob from client_data_blob.data")

    # Create the FinTS client
    client = FinTS3PinTanClient(
        bank_identifier=config.source.fints.blz,
        user_id=config.source.fints.username,
        pin=config.source.fints.password,
        server=config.source.fints.host,
        product_id=config.source.fints.product_id,
        from_data=from_data,
    )

    # source_account: SEPAAccount = SEPAAccount(
    #     iban=config.source.fints.iban,
    #     bic=config.source.fints.bic,
    #     accountnumber=config.source.fints.iban[-10:],
    #     subaccount=None,
    #     blz=config.source.fints.blz
    # )

    with client:
        if client.init_tan_response:
            do_tan(client.init_tan_response)

        print("Connected to bank.")

        accounts = client.get_sepa_accounts()
        for account in accounts:
            print(f"Account: {account}")
            if account.iban == config.source.fints.iban:
                source_account = account
                break

        # hispas = client.bpd.find_segment_first("HISPAS")
        # offered = hispas.parameter.supported_sepa_formats
        # print("Bank advertises:", offered)

    try:
        input("Press enter to continue...")
    
        loop(config, client, source_account)

    finally:
        dataBlob = client.deconstruct(including_private=True) # as bytes
        with open("client_data_blob.data", "wb") as f:
            f.write(dataBlob)
        print("Data blob saved to client_data_blob.data")